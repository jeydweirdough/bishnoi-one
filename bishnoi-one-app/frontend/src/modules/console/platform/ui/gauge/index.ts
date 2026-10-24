// Gauge UI (https://gauge-ui.dev, MIT, github.com/thordursk/gauge-ui), as published
// 2026-10-10; only the class helper's import is changed. Use it through ../health-gauge.tsx.
export { Gauge, type GaugeFit, type GaugeProps } from "@/src/modules/console/platform/ui/gauge/gauge"
export { GaugeInset, type GaugeInsetProps } from "@/src/modules/console/platform/ui/gauge/inset"
export {
  useGauge,
  type GaugeContextValue,
  type GaugeDomainProps,
} from "@/src/modules/console/platform/ui/gauge/context"
export {
  GaugeTrack,
  GaugeArc,
  GaugeStack,
  GaugeZones,
  type GaugeArcProps,
  type GaugeStackPart,
  type GaugeStackProps,
  type GaugeZonesProps,
} from "@/src/modules/console/platform/ui/gauge/arcs"
export { GaugeControl, type GaugeControlProps } from "@/src/modules/console/platform/ui/gauge/control"
export {
  GaugeTicks,
  GaugeMarks,
  GaugeTickLabels,
  type GaugeTicksProps,
  type GaugeMarksProps,
  type GaugeTickLabelsProps,
} from "@/src/modules/console/platform/ui/gauge/ticks"
export {
  GaugeText,
  GaugeValue,
  type GaugeTextProps,
  type GaugeValueProps,
} from "@/src/modules/console/platform/ui/gauge/text"
export { GaugeDot, type GaugeDotProps } from "@/src/modules/console/platform/ui/gauge/dot"
export {
  GaugeTooltip,
  type GaugeTooltipPosition,
  type GaugeTooltipProps,
  type GaugeTooltipSide,
} from "@/src/modules/console/platform/ui/gauge/tooltip"
export {
  GaugeNeedle,
  GaugeHub,
  type GaugeNeedleProps,
  type GaugeHubProps,
} from "@/src/modules/console/platform/ui/gauge/needle"
export {
  angleToValue,
  arcBox,
  arcPath,
  clamp,
  cutValues,
  degreesToRadians,
  polar,
  stepValues,
  valueToAngle,
  valueToTurnedAngle,
} from "@/src/modules/console/platform/ui/gauge/math"
export {
  clockLabel,
  clockTime,
  compassLabel,
  durationLabel,
  fadeColor,
  fontClass,
  weightClass,
  zoneColor,
  zoneCutoffs,
  type FontFamily,
  type FontWeight,
  type NeedleStyle,
  type StrokeCap,
  type TextAnchor,
  type Zone,
} from "@/src/modules/console/platform/ui/gauge/utils"
export {
  DEFAULT_TRANSITION,
  cubicBezier,
  easingFunction,
  resolveTransition,
  springPhysics,
  stepSpring,
  type GaugeEasing,
  type GaugeSpringTransition,
  type GaugeTransition,
  type GaugeTweenTransition,
} from "@/src/modules/console/platform/ui/gauge/transition"
export { useAnimatedValue } from "@/src/modules/console/platform/ui/gauge/use-animated-value"
