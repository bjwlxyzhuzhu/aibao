// 线性图标（24×24，描边 1.8），风格与设计稿一致
import type { SVGProps } from 'react'

type P = SVGProps<SVGSVGElement> & { size?: number }
const S = ({ size = 20, children, ...p }: P & { children: React.ReactNode }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round" {...p}>{children}</svg>
)

export const IHome = (p: P) => <S {...p}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V20h5v-5h4v5h5V9.5" /></S>
export const ISearch = (p: P) => <S {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></S>
export const IClip = (p: P) => <S {...p}><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4V3h6v1M9 10h6M9 14h4" /></S>
export const IUsers = (p: P) => <S {...p}><circle cx="9" cy="8" r="3.2" /><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" /><circle cx="17" cy="9" r="2.5" /><path d="M16 14.2c2.4.2 4 1.8 4.5 4.8" /></S>
export const IBook = (p: P) => <S {...p}><path d="M4 5.5C4 4.7 4.7 4 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5z" /><path d="M20 5.5c0-.8-.7-1.5-1.5-1.5H13v16h5.5c.8 0 1.5-.7 1.5-1.5z" /></S>
export const IBell = (p: P) => <S {...p}><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z" /><path d="M10 20a2 2 0 0 0 4 0" /></S>
export const IChevron = (p: P) => <S {...p}><path d="m9 6 6 6-6 6" /></S>
export const IBack = (p: P) => <S {...p}><path d="M19 12H5M11 6l-6 6 6 6" /></S>
export const IArrow = (p: P) => <S {...p}><path d="M5 12h14M13 6l6 6-6 6" /></S>
export const ICamera = (p: P) => <S {...p}><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></S>
export const IMic = (p: P) => <S {...p}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></S>
export const ICheck = (p: P) => <S {...p}><path d="m5 12 4.5 4.5L19 7" /></S>
export const IX = (p: P) => <S {...p}><path d="M6 6l12 12M18 6 6 18" /></S>
export const IAlert = (p: P) => <S {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.5v.01" /></S>
export const IBulb = (p: P) => <S {...p}><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3z" /></S>
export const ISettings = (p: P) => <S {...p}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" /></S>
export const IUpload = (p: P) => <S {...p}><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></S>
export const IPlay = (p: P) => <S {...p} fill="currentColor" stroke="none"><path d="M8 5.5v13l11-6.5z" /></S>
export const IPause = (p: P) => <S {...p} fill="currentColor" stroke="none"><rect x="7" y="5" width="3.5" height="14" rx="1" /><rect x="13.5" y="5" width="3.5" height="14" rx="1" /></S>
export const IStep = (p: P) => <S {...p}><path d="M6 5.5v13l9-6.5zM18 5v14" /></S>
export const ISend = (p: P) => <S {...p}><path d="M4 12 20 4l-6 16-3-7z" /></S>
export const IShield = (p: P) => <S {...p}><path d="M12 3 5 6v6c0 4.2 3 7.4 7 9 4-1.6 7-4.8 7-9V6z" /></S>
export const IFile = (p: P) => <S {...p}><path d="M14 3H6v18h12V7z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></S>
export const IDB = (p: P) => <S {...p}><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></S>
export const IClock = (p: P) => <S {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></S>
export const ILogout = (p: P) => <S {...p}><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" /></S>
export const IBed = (p: P) => <S {...p}><path d="M3 18V7M3 13h18v5M21 13a3 3 0 0 0-3-3h-7v3" /><circle cx="7" cy="10.5" r="1.6" /></S>
export const IFood = (p: P) => <S {...p}><path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M16 3c-2 1.5-2 6 0 7.5V21" /></S>
export const IDrop = (p: P) => <S {...p}><path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z" /></S>
export const ISun = (p: P) => <S {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></S>
export const IDoor = (p: P) => <S {...p}><path d="M14 3H7v18h7" /><path d="M14 3l5 2v14l-5 2z" /><path d="M11 12h.01" /></S>
export const IPen = (p: P) => <S {...p}><path d="M4 20h4L19 9l-4-4L4 16z" /></S>
export const ISpray = (p: P) => <S {...p}><path d="M8 9h6v12H8zM9 9V6h4v3M13 4h3M18 3l1 1M18 6h2M18 8l1 1" /></S>
