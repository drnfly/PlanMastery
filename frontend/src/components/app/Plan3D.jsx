import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const COLORS = { exterior: "#F59E0B", interior: "#22D3EE" };

const Controls = ({ target }) => {
  const { camera, gl } = useThree();
  useEffect(() => {
    const c = new OrbitControls(camera, gl.domElement);
    c.target.set(...target); c.enableDamping = true; c.maxPolarAngle = Math.PI / 2.05; c.update();
    let raf; const loop = () => { c.update(); raf = requestAnimationFrame(loop); }; loop();
    return () => { cancelAnimationFrame(raf); c.dispose(); };
  }, [camera, gl, target]);
  return null;
};

const Wall = ({ w, delay }) => {
  const ref = useRef();
  const start = useRef(null);
  useFrame(({ clock }) => {
    if (start.current === null) start.current = clock.elapsedTime;
    const t = Math.min(Math.max((clock.elapsedTime - start.current - delay) / 0.9, 0), 1);
    ref.current.scale.y = Math.max(1 - Math.pow(1 - t, 3), 0.001);
  });
  return (
    <group position={[w.cx, 0, w.cz]} rotation={[0, w.rot, 0]} ref={ref}>
      <mesh position={[0, w.h / 2, 0]} castShadow>
        <boxGeometry args={[w.len, w.h, w.t]} />
        <meshStandardMaterial color={COLORS[w.type] || COLORS.interior} transparent opacity={0.92} roughness={0.6} />
      </mesh>
    </group>
  );
};

const Scene = ({ url, model }) => {
  const tex = useLoader(THREE.TextureLoader, url);
  tex.colorSpace = THREE.SRGBColorSpace;
  const { W, H, walls, target, F } = useMemo(() => {
    const b = model.plan_bbox || { x1: 0, x2: 1000 };
    const frac = Math.max((b.x2 - b.x1) / 1000, 0.05);
    const W = model.plan_width_ft > 0 ? model.plan_width_ft / frac : 100;
    const H = W * (tex.image.height / tex.image.width);
    const P = (x, y) => [(x / 1000) * W - W / 2, (y / 1000) * H - H / 2];
    const h = model.wall_height_ft || 9;
    const walls = (model.walls || []).map((w) => {
      const [ax, az] = P(w.x1, w.y1); const [bx, bz] = P(w.x2, w.y2);
      return { cx: (ax + bx) / 2, cz: (az + bz) / 2, len: Math.hypot(bx - ax, bz - az) || 0.1,
        rot: -Math.atan2(bz - az, bx - ax), t: Math.max((w.thickness_in || 6) / 12, 0.35), h, type: w.type };
    });
    const [tx, tz] = P(((b.x1 || 0) + (b.x2 || 1000)) / 2, ((b.y1 || 0) + (b.y2 || 1000)) / 2);
    return { W, H, walls, target: [tx, 0, tz], F: Math.max(model.plan_width_ft || 40, 20) };
  }, [model, tex]);
  const { camera } = useThree();
  useEffect(() => { camera.position.set(target[0] + F * 0.35, F * 0.85, target[2] + F * 1.05); }, [camera, target, F]);
  return (
    <>
      <ambientLight intensity={0.75} />
      <directionalLight position={[F, F * 1.5, F * 0.6]} intensity={1.1} />
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[W, H]} />
        <meshStandardMaterial map={tex} />
      </mesh>
      {walls.map((w, i) => <Wall key={i} w={w} delay={0.15 + i * 0.04} />)}
      <Controls target={target} />
    </>
  );
};

export const Plan3D = ({ url, model, replayKey }) => (
  <Canvas key={replayKey} camera={{ fov: 45, near: 0.1, far: 20000 }} data-testid="plan-3d-canvas" style={{ background: "#0A1220" }}>
    <Suspense fallback={null}><Scene url={url} model={model} /></Suspense>
  </Canvas>
);
