import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";

const color = {
  bg: "#F8FAFC",
  ink: "#101827",
  muted: "#607068",
  faint: "#E7EDE8",
  line: "#C9D4CC",
  trace: "#B9C5BE",
  traceSoft: "#EAF0EC",
  green: "#167C5C",
  greenDark: "#245F46",
  greenSoft: "#DFF5EA",
  blue: "#2F7DA6",
  blueSoft: "#E4F2F8",
  amber: "#D97706",
  amberSoft: "#FFF1D6",
  violet: "#6D5BD0",
  violetSoft: "#EEEAFB",
  white: "#FFFFFF",
};

type Mark = {
  x: number;
  y: number;
  w: number;
  strong: boolean;
};

type Facet = {
  label: string;
  text: string;
  source: string;
  color: string;
  soft: string;
  y: number;
  start: number;
  beamStart: number;
};

type Point = {
  x: number;
  y: number;
};

const core = { x: 636, y: 356 };

const facets: Facet[] = [
  {
    label: "Decision",
    text: "approved handoff",
    source: "[1] run_087",
    color: color.green,
    soft: color.greenSoft,
    y: 230,
    start: 176,
    beamStart: 130,
  },
  {
    label: "Constraint",
    text: "cite sources",
    source: "[1] run_087",
    color: color.blue,
    soft: color.blueSoft,
    y: 338,
    start: 202,
    beamStart: 154,
  },
  {
    label: "Preference",
    text: "custom profile",
    source: "[2] trace_119",
    color: color.amber,
    soft: color.amberSoft,
    y: 446,
    start: 228,
    beamStart: 178,
  },
];

const traceMarks: Mark[] = Array.from({ length: 132 }, (_, index) => {
  const row = index % 22;
  const col = Math.floor(index / 22);
  const wave = Math.sin(index * 1.73) * 10;

  return {
    x: 94 + col * 62 + wave,
    y: 138 + row * 21,
    w: 20 + ((index * 37) % 84),
    strong: index % 11 === 2 || index % 17 === 7,
  };
});

const noiseParticles = Array.from({ length: 44 }, (_, index) => ({
  x: 244 + (index % 8) * 34 + Math.sin(index) * 16,
  y: 164 + Math.floor(index / 8) * 58 + Math.cos(index * 1.4) * 18,
  delay: 56 + (index % 10) * 8,
  drift: -38 - (index % 5) * 13,
}));

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const tween = (
  frame: number,
  start: number,
  end: number,
  from = 0,
  to = 1,
) =>
  interpolate(frame, [start, end], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

const appear = (frame: number, start: number, end: number) =>
  tween(frame, start, end);

const disappear = (frame: number, start: number, end: number) =>
  1 - tween(frame, start, end);

const cubic = (a: number, b: number, c: number, d: number, t: number) => {
  const u = 1 - t;

  return u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d;
};

const point = (from: Point, c1: Point, c2: Point, to: Point, t: number): Point => ({
  x: cubic(from.x, c1.x, c2.x, to.x, t),
  y: cubic(from.y, c1.y, c2.y, to.y, t),
});

const path = (from: Point, c1: Point, c2: Point, to: Point) =>
  `M ${from.x} ${from.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${to.x} ${to.y}`;

const Text = ({
  children,
  x,
  y,
  size = 20,
  weight = 650,
  fill = color.ink,
  opacity = 1,
  mono = false,
  anchor = "start",
}: {
  children: React.ReactNode;
  x: number;
  y: number;
  size?: number;
  weight?: number;
  fill?: string;
  opacity?: number;
  mono?: boolean;
  anchor?: "start" | "middle" | "end";
}) => (
  <text
    x={x}
    y={y}
    fill={fill}
    fontFamily={
      mono
        ? "SFMono-Regular, ui-monospace, Menlo, monospace"
        : "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif"
    }
    fontSize={size}
    fontWeight={weight}
    letterSpacing={0}
    opacity={opacity}
    textAnchor={anchor}
  >
    {children}
  </text>
);

const Background = () => (
  <g>
    <defs>
      <radialGradient id="backgroundGlow" cx="50%" cy="46%" r="60%">
        <stop offset="0%" stopColor="#ECF7F1" />
        <stop offset="42%" stopColor="#F8FAFC" />
        <stop offset="100%" stopColor="#F8FAFC" />
      </radialGradient>
      <linearGradient id="coreGradient" x1="0%" x2="100%" y1="0%" y2="100%">
        <stop offset="0%" stopColor="#ECFFF6" />
        <stop offset="55%" stopColor="#FFFFFF" />
        <stop offset="100%" stopColor="#E7F5EF" />
      </linearGradient>
      <filter id="floatShadow" x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow dx="0" dy="18" stdDeviation="18" floodColor="#10251D" floodOpacity="0.12" />
      </filter>
      <filter id="smallShadow" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="0" dy="10" stdDeviation="9" floodColor="#10251D" floodOpacity="0.1" />
      </filter>
    </defs>
    <rect width="1280" height="720" fill="url(#backgroundGlow)" />
    <g opacity={0.42}>
      {Array.from({ length: 30 }).map((_, index) => (
        <path
          key={`guide-${index}`}
          d={`M 72 ${116 + index * 18} H 1208`}
          stroke={color.faint}
          strokeWidth={1}
        />
      ))}
    </g>
  </g>
);

const Header = ({ frame }: { frame: number }) => (
  <g opacity={appear(frame, 0, 24)}>
    <Text x={86} y={58} size={18} weight={850} fill={color.green} mono>
      LERIM
    </Text>
    <Text x={160} y={60} size={34} weight={850}>
      Trace compression with source memory
    </Text>
    <Text x={86} y={88} size={18} weight={600} fill={color.muted}>
      Lerim turns completed agent sessions into compact, cited context for the next run.
    </Text>
  </g>
);

const TraceField = ({ frame }: { frame: number }) => {
  const enter = appear(frame, 16, 48);
  const compress = appear(frame, 76, 144);
  const exit = disappear(frame, 244, 300);

  return (
    <g opacity={enter * exit}>
      <Text x={112} y={132} size={14} weight={850} fill={color.muted} mono>
        COMPLETED TRACE
      </Text>
      <g transform={`translate(${tween(frame, 16, 48, -18, 0)} 0)`}>
        {traceMarks.map((mark, index) => {
          const pull = compress * (1 + (index % 6) * 0.05);
          const opacity = mark.strong ? 0.5 + compress * 0.34 : 0.46 - compress * 0.28;
          const x = mark.x + pull * (core.x - mark.x) * 0.18;
          const y = mark.y + Math.sin(frame / 30 + index) * 1.8;

          return (
            <rect
              key={`trace-${index}`}
              x={x}
              y={y}
              width={mark.w * (mark.strong ? 1 : 0.82)}
              height={mark.strong ? 8 : 5}
              rx={4}
              fill={mark.strong ? color.trace : color.traceSoft}
              opacity={opacity}
            />
          );
        })}
        <path
          d="M 82 116 C 218 94, 402 108, 530 142"
          fill="none"
          stroke={color.line}
          strokeWidth={1.5}
          opacity={0.65}
        />
        <path
          d="M 80 608 C 236 642, 418 628, 540 582"
          fill="none"
          stroke={color.line}
          strokeWidth={1.5}
          opacity={0.65}
        />
      </g>
    </g>
  );
};

const Core = ({ frame }: { frame: number }) => {
  const enter = appear(frame, 54, 92);
  const pulse = appear(frame, 96, 138) * disappear(frame, 238, 276);
  const ring = 1 + pulse * 0.05;

  return (
    <g opacity={enter} filter="url(#floatShadow)">
      <g transform={`translate(${core.x} ${core.y}) scale(${ring}) translate(${-core.x} ${-core.y})`}>
        <path
          d={`M ${core.x} ${core.y - 122} L ${core.x + 106} ${core.y - 60} L ${core.x + 106} ${
            core.y + 60
          } L ${core.x} ${core.y + 122} L ${core.x - 106} ${core.y + 60} L ${core.x - 106} ${
            core.y - 60
          } Z`}
          fill="url(#coreGradient)"
          stroke={color.green}
          strokeWidth={2.2}
        />
        <path
          d={`M ${core.x - 106} ${core.y - 60} L ${core.x} ${core.y} L ${core.x + 106} ${
            core.y - 60
          }`}
          fill="none"
          stroke={color.green}
          strokeWidth={1.4}
          opacity={0.32}
        />
        <path
          d={`M ${core.x - 106} ${core.y + 60} L ${core.x} ${core.y} L ${core.x + 106} ${
            core.y + 60
          }`}
          fill="none"
          stroke={color.green}
          strokeWidth={1.4}
          opacity={0.32}
        />
        <circle cx={core.x} cy={core.y} r={48} fill={color.greenDark} />
        <Text x={core.x} y={core.y - 7} size={20} weight={850} fill={color.white} mono anchor="middle">
          LERIM
        </Text>
        <Text x={core.x} y={core.y + 18} size={13} weight={850} fill="#CFEBDD" mono anchor="middle">
          COMPILE
        </Text>
      </g>
      <g opacity={appear(frame, 104, 142)}>
        <Text x={core.x - 142} y={core.y - 132} size={13} weight={850} fill={color.muted} mono>
          FILTER
        </Text>
        <Text x={core.x - 24} y={core.y - 154} size={13} weight={850} fill={color.muted} mono>
          EXTRACT
        </Text>
        <Text x={core.x + 96} y={core.y - 132} size={13} weight={850} fill={color.muted} mono>
          CITE
        </Text>
      </g>
    </g>
  );
};

const NoiseEvaporation = ({ frame }: { frame: number }) => (
  <g>
    {noiseParticles.map((particle, index) => {
      const move = appear(frame, particle.delay, particle.delay + 70);
      const fade = disappear(frame, particle.delay + 28, particle.delay + 74);
      const from = { x: particle.x, y: particle.y };
      const to = { x: core.x - 38 + (index % 7) * 12, y: core.y + particle.drift };
      const p = point(from, { x: 460, y: from.y }, { x: 524, y: to.y }, to, move);

      return (
        <circle
          key={`noise-${index}`}
          cx={p.x}
          cy={p.y}
          r={2.3 + (index % 3)}
          fill={index % 4 === 0 ? color.amber : color.trace}
          opacity={0.38 * move * fade}
        />
      );
    })}
  </g>
);

const SourceChip = ({
  x,
  y,
  text,
  fill,
  tint,
  opacity = 1,
}: {
  x: number;
  y: number;
  text: string;
  fill: string;
  tint: string;
  opacity?: number;
}) => {
  const width = 24 + text.length * 8;

  return (
    <g opacity={opacity}>
      <rect x={x} y={y} width={width} height={28} rx={8} fill={tint} />
      <Text x={x + 12} y={y + 19} size={13} weight={850} fill={fill} mono>
        {text}
      </Text>
    </g>
  );
};

const Beams = ({ frame }: { frame: number }) => (
  <g>
    {facets.map((facet, index) => {
      const progress = appear(frame, facet.beamStart, facet.beamStart + 72);
      const from = { x: core.x + 94, y: core.y - 38 + index * 38 };
      const to = { x: 852, y: facet.y };
      const d = path(from, { x: 724, y: from.y }, { x: 760, y: to.y }, to);
      const particle = point(from, { x: 724, y: from.y }, { x: 760, y: to.y }, to, progress);

      return (
        <g key={`beam-${facet.label}`}>
          <path
            d={d}
            fill="none"
            stroke={facet.color}
            strokeWidth={3}
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - progress}
            opacity={0.5 * progress}
          />
          <circle
            cx={particle.x}
            cy={particle.y}
            r={7}
            fill={facet.color}
            opacity={progress * disappear(frame, facet.beamStart + 64, facet.beamStart + 88)}
          />
        </g>
      );
    })}
  </g>
);

const FacetShape = ({ facet, frame, index }: { facet: Facet; frame: number; index: number }) => {
  const show = appear(frame, facet.start, facet.start + 40);
  const x = 858;
  const y = facet.y - 38;
  const w = 312;
  const h = 76;
  const slide = tween(frame, facet.start, facet.start + 40, 34, 0);
  const active = appear(frame, 260 + index * 12, 282 + index * 12) * disappear(frame, 332, 350);

  return (
    <g opacity={show} transform={`translate(${slide} ${-active * 6})`} filter="url(#smallShadow)">
      <path
        d={`M ${x + 24} ${y} H ${x + w} L ${x + w - 24} ${y + h} H ${x} Z`}
        fill={facet.soft}
        stroke={facet.color}
        strokeWidth={1.8}
      />
      <path
        d={`M ${x + 24} ${y} H ${x + w} L ${x + w - 24} ${y + h} H ${x} Z`}
        fill={color.white}
        opacity={0.45}
      />
      <circle cx={x + 28} cy={y + 38} r={8} fill={facet.color} />
      <Text x={x + 50} y={y + 34} size={16} weight={850} fill={facet.color}>
        {facet.label}
      </Text>
      <Text x={x + 50} y={y + 58} size={19} weight={700}>
        {facet.text}
      </Text>
      <SourceChip x={x + 186} y={y + 20} text={facet.source} fill={facet.color} tint={facet.soft} />
    </g>
  );
};

const ContextCrystal = ({ frame }: { frame: number }) => {
  const show = appear(frame, 150, 190);
  const spine = appear(frame, 210, 252);
  const final = appear(frame, 286, 326);

  return (
    <g opacity={show}>
      <Text x={856} y={132} size={14} weight={850} fill={color.muted} mono>
        CITED CONTEXT
      </Text>
      <path
        d="M 826 182 V 500"
        stroke={color.line}
        strokeWidth={2}
        strokeDasharray="5 9"
        opacity={spine}
      />
      <Text x={826} y={532} size={13} weight={850} fill={color.muted} mono anchor="middle" opacity={spine}>
        EVIDENCE
      </Text>
      {facets.map((facet, index) => (
        <FacetShape key={facet.label} facet={facet} frame={frame} index={index} />
      ))}
      <g opacity={final}>
        <path
          d="M 882 566 H 1136"
          stroke={color.greenDark}
          strokeWidth={2.2}
          strokeLinecap="round"
        />
        <circle cx={880} cy={566} r={5} fill={color.greenDark} />
        <circle cx={1138} cy={566} r={5} fill={color.greenDark} />
        <Text x={1010} y={600} size={20} weight={780} fill={color.greenDark} anchor="middle">
          The next agent starts from cited context.
        </Text>
      </g>
    </g>
  );
};

const FinalLine = ({ frame }: { frame: number }) => (
  <g opacity={appear(frame, 310, 344)}>
    <Text x={640} y={670} size={22} weight={820} fill={color.greenDark} anchor="middle">
      {"Completed traces -> compact context -> cited answers"}
    </Text>
  </g>
);

export const TraceToAnswer = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <svg width="1280" height="720" viewBox="0 0 1280 720">
        <Background />
        <Header frame={frame} />
        <TraceField frame={frame} />
        <NoiseEvaporation frame={frame} />
        <Core frame={frame} />
        <Beams frame={frame} />
        <ContextCrystal frame={frame} />
        <FinalLine frame={frame} />
      </svg>
    </AbsoluteFill>
  );
};
