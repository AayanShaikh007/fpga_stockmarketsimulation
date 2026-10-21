// Update these steps and bump the version whenever a user-facing workflow changes.
export const GUIDE_VERSION = 'alpaca-paper-v2'
const STORAGE_KEY = 'nanoquant.guide.dismissed-version'

export const guideSteps = [
  { tag: 'WELCOME TO NANOQUANT', title: 'Your trading lab, explained.', body: 'Follow a price from its source to a decision. Explore with Python, then send the same inputs through your physical FPGA.', tip: 'All orders and fills are paper simulations. NanoQuant never places real trades.', visual: ['Market data', 'Decision engine', 'Your terminal'] },
  { tag: '01 / CHOOSE YOUR DATA', title: 'Start simple. Go live when ready.', body: 'Generated demo prices run continuously offline. Historical / offline replay plays a selected dataset and stops when it ends. The included DEMO has just 12 synthetic samples.', tip: 'For real AAPL, NVDA, or TSLA data, configure Alpaca keys in backend/.env; setup refreshes automatically, or use the Market data refresh icon. “Download symbol” selects a download target; the selected replay dataset decides what you actually run.', visual: ['Generated', 'Live IEX', 'Replay'] },
  { tag: '02 / PICK YOUR ENGINE', title: 'Python or physical hardware?', body: 'Python engine computes decisions on your PC. FPGA Live sends quotes to the Tang Nano 9K and checks every reply against Python. Your data source and engine are independent choices.', tip: 'For FPGA Live: load NanoQuant, select COM6 (or your detected port), press and release S2, then check the physical-reset confirmation. Reset before every new hardware run.', visual: ['Quote', 'Python / FPGA', 'Validated reply'] },
  { tag: '03 / TAKE CONTROL', title: 'You set the pace.', body: 'Press Start run and adjust the speed from 1–20 samples per second. Stop ends generation; it does not liquidate a position. Only the browser tab that started a run can control it.', tip: 'Kill requests a latched trading stop. Wait for acknowledgment. Clear a hardware kill with physical S2 reset; failed trades are never automatically resent.', visual: ['Start', 'Adjust speed', 'Stop / kill'] },
  { tag: '04 / READ THE CHART', title: 'Every marker has a story.', body: 'Green BUY and red SELL markers show nonzero engine decisions. Click a marker or its recent-trade button to inspect input price, sequence, risk checks, paper fill, and host response time.', tip: 'Real stock prices appear in USD. The FPGA receives basis-point ticks around a fixed session anchor. “Matched” means a physical reply agreed with Python; “Reference” is Python only.', visual: ['Price', 'BUY / SELL', 'Inspect'] },
  { tag: '05 / WATCH YOUR PORTFOLIO', title: 'Paper money. Visible outcomes.', body: 'Choose Local $10,000 for a fresh simulated portfolio each run, or Alpaca PAPER for its persistent virtual account. Alpaca mode requires live prices, explicit order consent, and an open regular market session. Broker orders appear on Alpaca?s website.', tip: 'A signal is not necessarily a fill. Alpaca holdings survive new runs; stop/kill does not liquidate them. No real-money host is supported. Strategy editing and backend-to-FPGA strategy deployment are future work, not available features.', visual: ['$10,000', 'Paper fills', 'Equity + P&L'] },
  { tag: '06 / UNDERSTAND THE NUMBERS', title: 'Measure what actually happened.', body: 'The engineering monitor separates measured host round trips, measured Python computation, UART errors, and skipped market samples. Live-data API errors never fall back to invented prices.', tip: 'One FPGA cycle at 27 MHz is about 37 ns by architecture—not independently measured physical latency. FPGA packet-drop counts are unavailable in the current protocol.', visual: ['Host RTT', 'Error counters', 'Clear provenance'] },
]

type GuideStorage = Pick<Storage, 'getItem' | 'setItem'>
function browserStorage(): GuideStorage | null {
  try { return typeof window === 'undefined' ? null : window.localStorage } catch { return null }
}
export function shouldShowGuide(storage: GuideStorage | null = browserStorage()): boolean {
  try { return storage?.getItem(STORAGE_KEY) !== GUIDE_VERSION } catch { return true }
}
export function rememberGuide(storage: GuideStorage | null = browserStorage()): void {
  try { storage?.setItem(STORAGE_KEY, GUIDE_VERSION) } catch { /* The guide remains usable without storage. */ }
}
