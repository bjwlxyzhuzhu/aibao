import { IBed, IDoor, IDrop, IFood, IHome, IPen, ISun } from './icons'

export const SEG_ICON: Record<string, (p: { size?: number }) => JSX.Element> = {
  入园: IHome, 进餐: IFood, 盥洗: IDrop, 教学: IPen, 户外: ISun, 午睡: IBed, 离园: IDoor,
}
export const SEGMENTS = ['入园', '进餐', '盥洗', '教学', '户外', '午睡', '离园']
export const CATEGORIES = ['安全', '卫生', '健康', '膳食', '设施', '保教', '生活照料']

export function SegIcon({ seg, size = 20 }: { seg: string; size?: number }) {
  const I = SEG_ICON[seg] || IPen
  return <I size={size} />
}

// 热力色阶（设计稿：浅杏 → 赤陶）
export const HEAT = ['#FCEDE6', '#F8D9CB', '#F2BCA6', '#E99A7E', '#DB7356', '#C9583C']
export function heatColor(v: number, max: number) {
  if (v <= 0) return HEAT[0]
  const i = Math.min(HEAT.length - 1, 1 + Math.floor(((v - 1) / Math.max(1, max - 0.999)) * (HEAT.length - 2)))
  return HEAT[i]
}
