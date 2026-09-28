/**
 * Purchase-moment feedback: a confetti burst and a short "cha-ching" made with the Web Audio API
 * (no audio files). Respects the shopper's mute setting and prefers-reduced-motion.
 */

const MUTE_KEY = 'cc_sound_muted'
const COLORS = ['#0c233f', '#7ba0c5', '#ffffff', '#f2c14e', '#3a7bc8']

export function isMuted(): boolean {
  return localStorage.getItem(MUTE_KEY) === '1'
}

export function setMuted(muted: boolean) {
  localStorage.setItem(MUTE_KEY, muted ? '1' : '0')
}

function reducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

let audio: AudioContext | null = null

/** Register-style "cha-ching": a soft click, then two bright bell tones. */
export function playChaChing() {
  if (isMuted()) return
  try {
    audio ??= new AudioContext()
    const ctx = audio
    const now = ctx.currentTime

    // Click: a tiny burst of filtered noise.
    const noise = ctx.createBuffer(1, ctx.sampleRate * 0.03, ctx.sampleRate)
    const data = noise.getChannelData(0)
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length)
    const click = ctx.createBufferSource()
    click.buffer = noise
    const clickGain = ctx.createGain()
    clickGain.gain.value = 0.25
    click.connect(clickGain).connect(ctx.destination)
    click.start(now)

    // "Cha-ching": two quick bell notes (E6 then A6).
    ;[
      [1318.5, 0.06],
      [1760, 0.16],
    ].forEach(([freq, start]) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'triangle'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, now + start)
      gain.gain.exponentialRampToValueAtTime(0.22, now + start + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + start + 0.45)
      osc.connect(gain).connect(ctx.destination)
      osc.start(now + start)
      osc.stop(now + start + 0.5)
    })
  } catch {
    // Audio is a nice-to-have; never let it break adding to the bag.
  }
}

/** Confetti burst from an element (e.g. the Add to Bag button). `big` = full-screen shower for checkout. */
export function confettiFrom(el: Element | null, big = false) {
  if (reducedMotion()) return
  const rect = el?.getBoundingClientRect()
  const originX = rect ? rect.left + rect.width / 2 : window.innerWidth / 2
  const originY = rect ? rect.top + rect.height / 2 : window.innerHeight / 3
  const count = big ? 140 : 60
  const layer = document.createElement('div')
  layer.className = 'confetti-layer'
  document.body.appendChild(layer)

  for (let i = 0; i < count; i++) {
    const piece = document.createElement('span')
    piece.className = 'confetti'
    piece.style.background = COLORS[i % COLORS.length]
    piece.style.left = `${originX}px`
    piece.style.top = `${originY}px`
    if (i % 3 === 0) piece.style.borderRadius = '50%'
    layer.appendChild(piece)

    const angle = big ? Math.random() * Math.PI * 2 : -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 0.9
    const speed = (big ? 380 : 220) + Math.random() * (big ? 420 : 220)
    const dx = Math.cos(angle) * speed
    const dy = Math.sin(angle) * speed
    piece.animate(
      [
        { transform: 'translate(0, 0) rotate(0deg)', opacity: 1 },
        { transform: `translate(${dx}px, ${dy + 380}px) rotate(${Math.random() * 720 - 360}deg)`, opacity: 0 },
      ],
      { duration: 1100 + Math.random() * 700, easing: 'cubic-bezier(.15,.7,.4,1)', fill: 'forwards' },
    )
  }
  setTimeout(() => layer.remove(), 2000)
}

/** Everything that happens on a purchase action. */
export function celebrate(el: Element | null, big = false) {
  playChaChing()
  confettiFrom(el, big)
}
