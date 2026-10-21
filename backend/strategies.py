"""Validated declarative strategies. Files contain data, never executable Python."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from nanoquant.model import Engine


class Strategy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    name: str = Field(default='Untitled strategy', min_length=1, max_length=100)
    hypothesis: str = Field(default='', max_length=5000)
    kind: Literal['anchor', 'sma_reversion'] = 'anchor'
    threshold_ticks: int = Field(default=5, ge=1, le=500)
    window: int = Field(default=20, ge=2, le=500)
    max_order: int = Field(default=20, ge=1, le=20)
    position_limit: int = Field(default=100, ge=1, le=100)


BUILTIN = Strategy(name='Original fixed-anchor strategy')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def fpga_supported(spec):
    return spec.kind == 'anchor' and (spec.threshold_ticks,spec.max_order,spec.position_limit)==(5,20,100)


class StrategyEngine:
    def __init__(self, spec):
        self.spec = spec
        self.engine = Engine(threshold=spec.threshold_ticks,max_order=spec.max_order,limit=spec.position_limit)
        self.history = deque(maxlen=spec.window)

    def step(self, quote):
        if self.spec.kind == 'sma_reversion':
            # Only past samples form the moving reference; current sample is appended afterwards.
            if len(self.history) < self.spec.window and not quote.kill and not self.engine.killed:
                self.history.append(quote.price)
                return 0,self.engine.position,0
            if self.history:
                self.engine.fair = sum(self.history)//len(self.history)
        result = self.engine.step(quote)
        self.history.append(quote.price)
        return result


class Conflict(ValueError):
    pass


class StrategyStore:
    def __init__(self, root=None):
        self.root = root or Path(__file__).parent/'data'/'research'
        self.lock = threading.RLock()

    def path(self, identifier, folder='strategies'):
        if not re.fullmatch('[a-f0-9]{32}',identifier):
            raise ValueError('Invalid research file ID')
        return self.root/folder/f'{identifier}.json'

    def atomic(self, path, value):
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp = tempfile.mkstemp(dir=path.parent,suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as file:
                json.dump(value,file,indent=2);file.flush();os.fsync(file.fileno())
            os.replace(temp,path)
        finally:
            if os.path.exists(temp): os.unlink(temp)

    def get(self, identifier):
        path=self.path(identifier)
        if not path.exists(): raise ValueError('Strategy file not found')
        data=json.loads(path.read_text(encoding='utf-8'))
        Strategy(**data['spec'])
        return data

    def listing(self):
        return [self.get(path.stem) for path in sorted((self.root/'strategies').glob('*.json'))]

    def save(self, identifier, spec, expected_revision):
        with self.lock:
            old=self.get(identifier) if identifier else None
            if old and old['revision'] != expected_revision:
                raise Conflict('Another save changed this file. Reload or save a recovery copy.')
            identifier=identifier or uuid4().hex
            if old:
                self.atomic(self.root/'backups'/identifier/f"{old['revision']}.json",old)
            value={'id':identifier,'revision':old['revision']+1 if old else 1,
                   'spec':spec.model_dump(),'fpga_supported':fpga_supported(spec)}
            self.atomic(self.path(identifier),value)
            return value

    def freeze(self, identifier, revision):
        with self.lock:
            saved=self.get(identifier)
            if saved['revision']!=revision: raise Conflict('Save the current strategy before freezing')
            snapshot=dict(saved,id=uuid4().hex,source_id=identifier,sha256=digest(saved['spec']))
            self.atomic(self.path(snapshot['id'],'snapshots'),snapshot)
            return snapshot

    def snapshot(self, identifier):
        path=self.path(identifier,'snapshots')
        if not path.exists(): raise ValueError('Frozen strategy not found')
        saved=json.loads(path.read_text(encoding='utf-8'))
        if digest(saved['spec'])!=saved['sha256']: raise ValueError('Frozen strategy checksum mismatch')
        Strategy(**saved['spec'])
        return saved

    def backups(self,identifier):
        self.path(identifier)
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((self.root/'backups'/identifier).glob('*.json'),key=lambda p:int(p.stem))]

    def restore(self,identifier,revision,expected):
        with self.lock:
            selected=next((v for v in self.backups(identifier) if v['revision']==revision),None)
            if not selected: raise ValueError('Backup revision not found')
            return self.save(identifier,Strategy(**selected['spec']),expected)
