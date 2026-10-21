import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Sparkles, X } from 'lucide-react'
import { guideSteps } from './onboardingContent'

export default function Onboarding({ open, onDismiss }: { open: boolean; onDismiss: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [step,setStep] = useState(0)
  const content = guideSteps[step]
  const last = step === guideSteps.length-1
  useEffect(() => {
    const element = dialog.current
    if (!element) return
    if (open) { setStep(0); if (!element.open) element.showModal() }
    else if (element.open) element.close()
    return () => { if (element.open) element.close() }
  }, [open])
  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previous }
  }, [open])
  return <dialog ref={dialog} className="onboarding" aria-labelledby="guide-title" aria-describedby="guide-description" onCancel={event => { event.preventDefault(); onDismiss() }}>
    <button className="guide-close icon-button" aria-label="Close introduction" onClick={onDismiss}><X size={18}/></button>
    <div className="guide-top"><span className="guide-symbol"><Sparkles size={22}/></span><span>NANOQUANT <span>/ QUICK START</span></span></div>
    <div className="guide-step" key={step}>
      <div className="guide-visual" aria-hidden="true"><span className="guide-orbit"/>{content.visual.map((label,index) => <div key={label} className={`guide-node node-${index}`}><span>{index === 2 ? <Check size={15}/> : index+1}</span><small>{label}</small></div>)}</div>
      <div className="guide-eyebrow">{content.tag}</div><h2 id="guide-title">{content.title}</h2><p id="guide-description">{content.body}</p><div className="guide-tip">{content.tip}</div>
    </div>
    <div className="guide-progress"><span>Step {step+1} of {guideSteps.length}</span><div aria-label="Introduction steps">{guideSteps.map((item,index) => <button key={item.tag} aria-label={`Go to step ${index+1}: ${item.title}`} aria-current={index === step ? 'step' : undefined} className={index === step ? 'current' : index < step ? 'done' : ''} onClick={() => setStep(index)}/>)}</div></div>
    <div className="guide-actions"><button className="guide-skip" onClick={onDismiss}>Skip introduction</button><div>{step > 0 && <button className="button secondary" onClick={() => setStep(step-1)}><ArrowLeft size={14}/> Back</button>}<button className="button primary" onClick={() => last ? onDismiss() : setStep(step+1)}>{last ? 'Open my terminal' : step === 0 ? 'Show me around' : 'Next'}<ArrowRight size={14}/></button></div></div>
    <p className="guide-reopen">You can reopen this guide from “Introduction” in the top bar.</p>
  </dialog>
}
