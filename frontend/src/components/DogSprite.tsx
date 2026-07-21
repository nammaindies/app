// Placeholder pariah-dog sprite — prick ears, sickle tail, lean frame.
// Hand-plotted pixel map; a real pixel artist replaces this later.
// One mark, a few coats; rendered crisp (no anti-aliasing) at any scale.

export type Coat = "tan" | "black" | "piebald" | "brindle" | "ghost";

const COATS: Record<Coat, { B: string; S: string }> = {
  tan: { B: "#c8863f", S: "#9c5f2c" },
  black: { B: "#4a3b2f", S: "#2c2119" },
  piebald: { B: "#e7d9c3", S: "#b98f5f" },
  brindle: { B: "#8a5a34", S: "#573620" },
  ghost: { B: "#b3a99a", S: "#8b8172" },
};

const OUTLINE = "#33241b";
const EYE = "#f7eee0";

// 18 wide × 14 tall. '#' outline · 'B' coat · 'S' shade · 'o' eye.
const DOG = [
  "                  ",
  "            ##    ",
  "  ##       #BB#   ",
  " #BB#     #BBBB#  ",
  " #BS#    #BBBBBB# ",
  " #BBB####BBBBBB#  ",
  "  #BBBBBBBBBBB#o  ",
  "  #BSBBBBBBBBB##  ",
  "  #BBBBBBBBBBB#   ",
  "  #BBBBBBBBBBB#   ",
  "  #B##B##B##B#    ",
  "  #B##B##B##B#    ",
  "  ## ## ## ##     ",
  "                  ",
];

export default function DogSprite({
  coat = "tan",
  scale = 6,
  className,
}: {
  coat?: Coat;
  scale?: number;
  className?: string;
}) {
  const pal = COATS[coat];
  const paint: Record<string, string> = {
    "#": OUTLINE,
    B: pal.B,
    S: pal.S,
    o: EYE,
  };
  const w = DOG[0].length;
  const h = DOG.length;
  const rects: JSX.Element[] = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const ch = DOG[y][x];
      const fill = paint[ch];
      if (!fill) continue;
      rects.push(<rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={fill} />);
    }
  }
  return (
    <svg
      className={className}
      width={w * scale}
      height={h * scale}
      viewBox={`0 0 ${w} ${h}`}
      shapeRendering="crispEdges"
      aria-hidden="true"
      style={{ imageRendering: "pixelated", filter: `drop-shadow(0 ${Math.max(1, scale * 0.5)}px 0 rgba(51,36,27,0.35))` }}
    >
      {rects}
    </svg>
  );
}
