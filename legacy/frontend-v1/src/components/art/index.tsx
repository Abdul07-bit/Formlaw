// Original vector illustrations inspired by Indian legal & constitutional motifs.
// Deliberately avoids the State Emblem of India (restricted under the State Emblem
// of India (Prohibition of Improper Use) Act, 2005).

export function Chakra({ size = 64, color = '#0ea5e9', className }: { size?: number; color?: string; className?: string }) {
  const spokes = Array.from({ length: 24 }, (_, i) => i * 15)
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} className={className} aria-hidden>
      <circle cx="50" cy="50" r="46" fill="none" stroke={color} strokeWidth="4" />
      <circle cx="50" cy="50" r="8" fill={color} />
      {spokes.map((a) => (
        <g key={a} transform={`rotate(${a} 50 50)`}>
          <path d="M50 42 L48.6 12 L50 6 L51.4 12 Z" fill={color} />
          <circle cx="50" cy="5.5" r="1.6" fill={color} transform={`rotate(7.5 50 50)`} />
        </g>
      ))}
    </svg>
  )
}

export function SupremeCourtArt({ className }: { className?: string }) {
  const cols = (x0: number, n: number, gap: number, y: number, h: number) =>
    Array.from({ length: n }, (_, i) => <rect key={i} x={x0 + i * gap} y={y} width="7" height={h} rx="2" fill="url(#colGrad)" />)
  return (
    <svg viewBox="0 0 640 400" className={className} role="img" aria-label="Illustration of a domed Indian court building with colonnades and the national flag">
      <defs>
        <linearGradient id="skyG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#bae6fd" /><stop offset="1" stopColor="#f0f9ff" /></linearGradient>
        <linearGradient id="stoneG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#e0f2fe" /></linearGradient>
        <linearGradient id="domeG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#7dd3fc" /><stop offset="1" stopColor="#0284c7" /></linearGradient>
        <linearGradient id="colGrad" x1="0" x2="1"><stop offset="0" stopColor="#e0f2fe" /><stop offset=".5" stopColor="#ffffff" /><stop offset="1" stopColor="#bae6fd" /></linearGradient>
      </defs>
      <rect width="640" height="400" rx="32" fill="url(#skyG)" />
      <circle cx="520" cy="80" r="38" fill="#fde68a" opacity=".8" />
      <g fill="#fff" opacity=".9"><ellipse cx="120" cy="80" rx="46" ry="14" /><ellipse cx="150" cy="70" rx="30" ry="14" /><ellipse cx="420" cy="60" rx="36" ry="10" /></g>
      {/* lawn */}
      <path d="M0 330 Q320 300 640 330 V400 H0Z" fill="#86efac" opacity=".55" />
      {/* trees */}
      {[40, 80, 560, 600].map((x) => (<g key={x}><rect x={x - 3} y="280" width="6" height="40" fill="#78716c" /><circle cx={x} cy="270" r="22" fill="#22c55e" opacity=".85" /></g>))}
      {/* wings */}
      <rect x="110" y="215" width="420" height="105" rx="6" fill="url(#stoneG)" stroke="#bae6fd" strokeWidth="2" />
      <rect x="104" y="206" width="432" height="14" rx="4" fill="#e0f2fe" stroke="#7dd3fc" />
      {cols(122, 14, 14, 225, 82)}
      {cols(330, 14, 14.4, 225, 82)}
      {/* central block */}
      <rect x="255" y="175" width="130" height="145" rx="6" fill="#ffffff" stroke="#7dd3fc" strokeWidth="2" />
      <path d="M245 180 L320 140 L395 180 Z" fill="#e0f2fe" stroke="#38bdf8" strokeWidth="2" />
      {cols(268, 8, 15, 192, 115)}
      {/* drum + dome */}
      <rect x="282" y="112" width="76" height="30" rx="4" fill="#f0f9ff" stroke="#7dd3fc" strokeWidth="2" />
      <path d="M278 114 Q320 40 362 114 Z" fill="url(#domeG)" />
      <path d="M300 112 Q320 62 340 112" fill="none" stroke="#e0f2fe" strokeWidth="2" opacity=".6" />
      <rect x="317" y="40" width="6" height="26" fill="#0369a1" />
      {/* flag */}
      <line x1="320" y1="14" x2="320" y2="44" stroke="#334155" strokeWidth="2" />
      <g className="origin-left">
        <rect x="321" y="14" width="34" height="7" fill="#ff9933" />
        <rect x="321" y="21" width="34" height="7" fill="#ffffff" />
        <rect x="321" y="28" width="34" height="7" fill="#138808" />
        <circle cx="338" cy="24.5" r="2.6" fill="none" stroke="#000080" strokeWidth=".9" />
      </g>
      {/* steps */}
      {[0, 1, 2].map((i) => (<rect key={i} x={240 - i * 12} y={320 + i * 8} width={160 + i * 24} height="8" fill={i % 2 ? '#e0f2fe' : '#f8fafc'} stroke="#bae6fd" />))}
      {/* scales relief on pediment */}
      <g transform="translate(320 165)" stroke="#0284c7" strokeWidth="1.6" fill="none">
        <line x1="0" y1="-12" x2="0" y2="8" /><line x1="-12" y1="-8" x2="12" y2="-8" />
        <path d="M-12 -8 l-5 9 h10z M12 -8 l-5 9 h10z" fill="#bae6fd" />
      </g>
    </svg>
  )
}

export function ScalesArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} role="img" aria-label="Scales of justice">
      <defs><linearGradient id="sc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#38bdf8" /><stop offset="1" stopColor="#0369a1" /></linearGradient></defs>
      <circle cx="100" cy="100" r="96" fill="#f0f9ff" />
      <g stroke="url(#sc)" strokeWidth="6" strokeLinecap="round" fill="none">
        <line x1="100" y1="40" x2="100" y2="160" />
        <line x1="44" y1="62" x2="156" y2="62" />
        <line x1="70" y1="164" x2="130" y2="164" />
        <path d="M44 62 L24 112 M44 62 L64 112 M156 62 L136 112 M156 62 L176 112" strokeWidth="3" />
      </g>
      <path d="M20 112 Q44 140 68 112 Z" fill="url(#sc)" />
      <path d="M132 112 Q156 140 180 112 Z" fill="url(#sc)" />
      <circle cx="100" cy="36" r="9" fill="#ff9933" />
    </svg>
  )
}

export function ConstitutionArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 360 260" className={className} role="img" aria-label="Open book of the Constitution of India showing the opening words of the Preamble">
      <defs>
        <linearGradient id="pg" x1="0" x2="1"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#f0f9ff" /></linearGradient>
        <linearGradient id="cov" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#0ea5e9" /><stop offset="1" stopColor="#075985" /></linearGradient>
      </defs>
      <path d="M20 40 Q180 10 180 40 V240 Q180 214 20 238Z" fill="url(#cov)" transform="translate(-6 6)" />
      <path d="M340 40 Q180 10 180 40 V240 Q180 214 340 238Z" fill="url(#cov)" transform="translate(6 6)" />
      <path d="M20 36 Q180 6 180 36 V236 Q180 210 20 234Z" fill="url(#pg)" stroke="#bae6fd" strokeWidth="2" />
      <path d="M340 36 Q180 6 180 36 V236 Q180 210 340 234Z" fill="url(#pg)" stroke="#bae6fd" strokeWidth="2" />
      <text x="100" y="64" textAnchor="middle" fontFamily="Plus Jakarta Sans" fontWeight="800" fontSize="13" fill="#0b1b3f">THE CONSTITUTION</text>
      <text x="100" y="80" textAnchor="middle" fontFamily="Plus Jakarta Sans" fontWeight="800" fontSize="13" fill="#0b1b3f">OF INDIA</text>
      <g transform="translate(70 96)"><Chakra size={60} color="#0ea5e9" /></g>
      <text x="100" y="184" textAnchor="middle" fontFamily="Plus Jakarta Sans" fontWeight="700" fontSize="9" fill="#0369a1">Adopted 26 November 1949</text>
      <text x="260" y="62" textAnchor="middle" fontFamily="Plus Jakarta Sans" fontWeight="800" fontSize="12" fill="#0b1b3f">PREAMBLE</text>
      {['WE, THE PEOPLE OF INDIA,', 'having solemnly resolved to', 'constitute India into a', 'SOVEREIGN SOCIALIST SECULAR', 'DEMOCRATIC REPUBLIC and to', 'secure to all its citizens:', 'JUSTICE, social, economic', 'and political; LIBERTY …', 'EQUALITY … FRATERNITY …'].map((l, i) => (
        <text key={i} x="260" y={84 + i * 15} textAnchor="middle" fontFamily="Plus Jakarta Sans" fontWeight={/[A-Z]{4}/.test(l) ? 800 : 600} fontSize="9.5" fill="#3b4a6b">{l}</text>
      ))}
      <rect x="160" y="226" width="40" height="6" rx="3" fill="#ff9933" />
    </svg>
  )
}

export function GavelArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} role="img" aria-label="Judge's gavel">
      <circle cx="100" cy="100" r="96" fill="#e0f2fe" />
      <rect x="40" y="148" width="120" height="16" rx="6" fill="#0369a1" />
      <rect x="54" y="138" width="92" height="12" rx="5" fill="#0ea5e9" />
      <g transform="rotate(-35 100 90)">
        <rect x="92" y="70" width="16" height="96" rx="6" fill="#7c4a1e" />
        <rect x="58" y="44" width="84" height="40" rx="12" fill="#92400e" />
        <rect x="58" y="56" width="84" height="6" fill="#fbbf24" />
        <rect x="58" y="68" width="84" height="6" fill="#fbbf24" />
      </g>
    </svg>
  )
}

export function KycArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 220" className={className} role="img" aria-label="Identity card with face scan">
      <rect x="10" y="30" width="200" height="130" rx="18" fill="#fff" stroke="#bae6fd" strokeWidth="3" />
      <clipPath id="kycCard"><rect x="10" y="30" width="200" height="130" rx="18" /></clipPath>
      <g clipPath="url(#kycCard)">
        <rect x="10" y="30" width="67" height="9" fill="#ff9933" /><rect x="77" y="30" width="66" height="9" fill="#e2e8f0" /><rect x="143" y="30" width="67" height="9" fill="#138808" />
      </g>
      <circle cx="58" cy="96" r="26" fill="#bae6fd" />
      <circle cx="58" cy="88" r="10" fill="#0ea5e9" />
      <path d="M38 116 Q58 98 78 116" fill="#0ea5e9" />
      {[0, 1, 2, 3].map((i) => <rect key={i} x="100" y={70 + i * 16} width={i % 2 ? 70 : 90} height="7" rx="3.5" fill={i ? '#e0f2fe' : '#7dd3fc'} />)}
      <g transform="translate(220 60)">
        <rect width="90" height="120" rx="20" fill="#0b1b3f" />
        <circle cx="45" cy="54" r="22" fill="none" stroke="#38bdf8" strokeWidth="3" strokeDasharray="5 5" className="flow-line" />
        <circle cx="45" cy="50" r="8" fill="#38bdf8" />
        <path d="M31 70 Q45 58 59 70" stroke="#38bdf8" strokeWidth="4" fill="none" strokeLinecap="round" />
        <rect x="15" y="90" width="60" height="8" rx="4" fill="#22c55e" />
      </g>
    </svg>
  )
}
