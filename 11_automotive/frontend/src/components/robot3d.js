// @ts-nocheck
// 로봇 3D 모델 (로봇 3D 모델링.zip의 robot/robot.html 장면 코드를 함수로 옮김).
// 모드: 0 정상 · 1 주의 · 2 고장 · 3 정비중. 무대(three-d-stage)·버튼·화면 효과 DOM은 빼고, 점광원(사이렌·경광등·상태등)은
// 공장 장면 전체 셰이더를 바꾸므로 뺌. 고장 모드의 "E-07 모터 과열" 표지는 가짜 문구라 뺌.
// 단위 m, 바닥 y = 0, 정면 +z. 높이 약 0.8 m.
//   const R = createRobot(THREE); scene.add(R.root); R.setMode(3);  매 프레임 R.update(경과 초, dt, camera)
export function createRobot(THREE, opts = {}) { // opts.bubble = false: 말풍선 안 띄움 (작은 아이콘용)
  const V = (x, y) => new THREE.Vector2(x, y);

  const shell = new THREE.MeshStandardMaterial({ name: 'shell_white', color: 0xffffff, emissive: 0xe9ecef, emissiveIntensity: 0.32, roughness: 0.3, metalness: 0.0 });
  // Body shell with alert gradient (red from the bottom, pulsing upward)
  const uAlert = { value: 0 }, uTime = { value: 0 }, uBase = { value: 0 }, uTint = { value: new THREE.Color(0xf20505) };
  const bodyMat = shell.clone(); bodyMat.name = 'shell_white';
  bodyMat.customProgramCacheKey = () => 'alertBody';
  bodyMat.onBeforeCompile = s => {
    Object.assign(s.uniforms, { uAlert, uTime, uBase, uTint });
    s.vertexShader = s.vertexShader
      .replace('#include <common>', '#include <common>\nvarying float vWY;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWY = (modelMatrix * vec4(transformed, 1.0)).y;');
    s.fragmentShader = s.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vWY;\nuniform float uAlert, uTime, uBase;\nuniform vec3 uTint;')
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        float g = clamp((vWY - uBase) / 0.78, 0.0, 1.0);
        float wave = 0.5 + 0.5 * sin(uTime * 10.0 - g * 12.0);
        vec3 red = mix(uTint, mix(uTint, vec3(1.0), 0.4), g);
        float amt = uAlert * clamp(1.0 - g * 0.55, 0.0, 1.0) * (0.5 + 0.5 * wave);
        diffuseColor.rgb = mix(diffuseColor.rgb, red, amt);
        totalEmissiveRadiance = mix(totalEmissiveRadiance, red * 0.85, amt);`);
  };
  const seam = new THREE.MeshStandardMaterial({ name: 'seam_grey', color: 0xb9bcc0, roughness: 0.6, metalness: 0.0 });
  const visor = new THREE.MeshStandardMaterial({ name: 'screen_black', color: 0x030405, roughness: 0.85, metalness: 0.0 });
  const glassMat = new THREE.MeshPhysicalMaterial({ name: 'display_glass', color: 0x14171d, roughness: 0.04, metalness: 0.0, clearcoat: 1, clearcoatRoughness: 0.03, transparent: true, opacity: 0.42, depthWrite: false });
  const eye = new THREE.MeshStandardMaterial({ name: 'eye_blue', color: 0x3fb8ff, emissive: 0x2aa8ff, emissiveIntensity: 2.4, roughness: 0.4 });
  const blush = new THREE.MeshStandardMaterial({ name: 'blush_pink', color: 0xff8fb0, emissive: 0xff6f9c, emissiveIntensity: 0.9, roughness: 0.6, transparent: true, opacity: 0.75 });
  const glow = new THREE.MeshBasicMaterial({ name: 'eye_glow', color: 0x2aa8ff, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false });

  const robot = new THREE.Group(); robot.name = 'robot';
  const add = (name, geo, mat, cfg = {}, parent = robot) => {
    const m = new THREE.Mesh(geo, mat); m.name = name; m.castShadow = mat !== glow;
    if (cfg.p) m.position.set(...cfg.p);
    if (cfg.r) m.rotation.set(...cfg.r);
    if (cfg.s) m.scale.set(...cfg.s);
    parent.add(m); return m;
  };

  // Body — broad shoulders, long taper to a rounded point
  const bodyPts = [V(0,0), V(0.03,0.004), V(0.062,0.018), V(0.096,0.045), V(0.128,0.09), V(0.154,0.15),
    V(0.172,0.22), V(0.18,0.29), V(0.178,0.35), V(0.166,0.4), V(0.14,0.435), V(0.1,0.455), V(0.05,0.463), V(0,0.465)];
  add('body', new THREE.LatheGeometry(bodyPts, 72), bodyMat);
  add('body_seam', new THREE.TorusGeometry(0.17, 0.0018, 8, 96), seam, { p: [0, 0.385, 0], r: [Math.PI/2, 0, 0] });

  // Head group — floating ellipsoid with visor, eyes, seam
  const hs = [0.168, 0.145, 0.158], hy = 0.625;
  const head = new THREE.Group(); head.name = 'head_group'; head.position.y = hy; robot.add(head);
  add('head', new THREE.SphereGeometry(1, 64, 48), bodyMat, { s: hs }, head);
  add('head_seam', new THREE.TorusGeometry(1, 0.004, 8, 96, Math.PI), seam,
    { p: [0, -0.02, 0], r: [-Math.PI/2, 0, 0], s: [hs[0]*0.99, hs[2]*0.99, 1] }, head);
  // Display: matte black screen with eyes drawn on it, under a glossy glass cover
  const capGeo = () => new THREE.SphereGeometry(1, 64, 48, Math.PI/2 - 0.95, 1.9, Math.PI/2 - 0.62, 1.15);
  add('screen', capGeo(), visor, { s: hs.map(v => v * 1.012) }, head);
  const glass = add('display_glass', capGeo(), glassMat, { s: hs.map(v => v * 1.03) }, head);
  glass.castShadow = false; glass.renderOrder = 2;

  const eyes = [];
  for (const sx of [-1, 1]) {
    const x = 0.052 * sx;
    const z = hs[2] * 1.012 * Math.sqrt(1 - (x / (hs[0] * 1.012)) ** 2) + 0.0008;
    const g = new THREE.Group(); g.name = sx < 0 ? 'eye_L' : 'eye_R';
    g.position.set(x, -0.006, z); g.rotation.y = Math.atan2(x, z) * 0.9; head.add(g);
    add(g.name + '_arc', new THREE.TorusGeometry(0.026, 0.0075, 16, 40, Math.PI), eye, { s: [1, 0.85, 0.3] }, g);
    add(g.name + '_glow', new THREE.TorusGeometry(0.026, 0.017, 12, 40, Math.PI), glow, { p: [0, 0, 0.001], s: [1, 0.85, 0.3] }, g);
    const pn = new THREE.Group(); pn.name = g.name + '_panic'; pn.visible = false; pn.scale.x = -sx; g.add(pn);
    for (const sy of [1, -1]) {
      const dx = 0.027, dy = -0.013 * sy;
      add(g.name + (sy > 0 ? '_panic_top' : '_panic_bot'), new THREE.CapsuleGeometry(0.0065, Math.hypot(dx, dy), 6, 16), eye,
        { p: [-0.0015, -dy / 2, 0], r: [0, 0, Math.atan2(-dx, dy)], s: [1, 1, 0.3] }, pn);
    }
    g.userData.panic = pn;
    eyes.push(g);
    const bx = 0.092 * sx, bz = hs[2] * 1.012 * Math.sqrt(1 - (bx / (hs[0] * 1.012)) ** 2 - (0.03 / (hs[1] * 1.012)) ** 2) + 0.0008;
    add(sx < 0 ? 'blush_L' : 'blush_R', new THREE.CircleGeometry(0.016, 32), blush,
      { p: [bx, -0.03, bz], r: [0.2, Math.atan2(bx, bz), 0], s: [1.3, 0.75, 1] }, head);
  }

  // Arms — fins: wide at the shoulder, tapering down, pressed to the body
  const armPts = [V(0,0), V(0.014,0.006), V(0.026,0.03), V(0.035,0.07), V(0.04,0.12), V(0.04,0.17), V(0.034,0.2), V(0.02,0.218), V(0,0.222)];
  const arms = [];
  for (const sx of [-1, 1]) {
    const pv = new THREE.Group(); pv.name = sx < 0 ? 'shoulder_L' : 'shoulder_R';
    pv.position.set(0.2 * sx, 0.37, 0); pv.userData.sx = sx; robot.add(pv);
    add(sx < 0 ? 'arm_L' : 'arm_R', new THREE.LatheGeometry(armPts, 48), bodyMat,
      { p: [-0.035 * sx, -0.2, 0.0], r: [0, 0, -0.22 * sx], s: [1, 1, 1.5] }, pv);
    arms.push(pv);
  }

  const baseY = 0.05;
  robot.position.y = baseY;
  const root = new THREE.Group(); root.name = 'white_robot'; root.add(robot);
  // Warning sign "!" (stays upright, doesn't spin with the robot)
  const signMat = new THREE.MeshStandardMaterial({ name: 'sign_red', color: 0xff2a2a, emissive: 0xff1a1a, emissiveIntensity: 1.6, roughness: 0.4 });
  const sign = new THREE.Group(); sign.name = 'warning_sign'; sign.visible = false;
  const bar = new THREE.Mesh(new THREE.CapsuleGeometry(0.014, 0.06, 8, 16), signMat); bar.name = 'sign_bar'; bar.position.y = 0.05;
  const dot = new THREE.Mesh(new THREE.SphereGeometry(0.016, 24, 16), signMat); dot.name = 'sign_dot'; dot.position.y = -0.015;
  sign.add(bar, dot); root.add(sign);
  sign.position.set(0, baseY + 0.14 + 1.05 * (hy + 0.145) + 0.085, 0);

  // Danger FX: shockwave rings (원본의 사이렌 조명·화면 붉은 테두리는 뺌)
  const groundY = baseY + 0.002; // 원본 무대 바닥 = 몸 맨 아래
  const rings = [0, 1, 2].map(i => {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.9, 1, 64), new THREE.MeshBasicMaterial({ name: 'shockwave', color: 0xff2020, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
    m.name = 'shockwave_' + i; m.rotation.x = -Math.PI / 2; m.position.y = groundY; m.visible = false; root.add(m); return m;
  });
  const glassBase = glassMat.color.clone(), glassRed = new THREE.Color(0x5a0505);

  // ---------- Maintenance props ----------
  const metal = new THREE.MeshStandardMaterial({ name: 'tool_metal', color: 0xc3c9d1, roughness: 0.28, metalness: 0.35 });
  const darkMetal = new THREE.MeshStandardMaterial({ name: 'module_dark', color: 0x2a3038, roughness: 0.5, metalness: 0.2 });
  const housing = new THREE.MeshStandardMaterial({ name: 'module_grey', color: 0x8d96a1, roughness: 0.4, metalness: 0.25 });
  const hatYellow = new THREE.MeshStandardMaterial({ name: 'helmet_yellow', color: 0xffc21a, roughness: 0.35, metalness: 0.0 });
  const grip = new THREE.MeshStandardMaterial({ name: 'grip_orange', color: 0xff7a1a, roughness: 0.5, metalness: 0.0 });
  const wood = new THREE.MeshStandardMaterial({ name: 'hammer_wood', color: 0x9a6a3c, roughness: 0.7, metalness: 0.0 });
  const boxRed = new THREE.MeshStandardMaterial({ name: 'toolbox_red', color: 0xd8402e, roughness: 0.45, metalness: 0.1 });
  const stripeBlack = new THREE.MeshStandardMaterial({ name: 'stripe_black', color: 0x1b1c1f, roughness: 0.7 });
  const ledMat = new THREE.MeshStandardMaterial({ name: 'led', color: 0xff3030, emissive: 0xff2020, emissiveIntensity: 2 });
  const beaconMat = new THREE.MeshStandardMaterial({ name: 'beacon', color: 0xffb000, emissive: 0xffa000, emissiveIntensity: 2 });
  const hatchLed = new THREE.MeshStandardMaterial({ name: 'hatch_led', color: 0x2ee87a, emissive: 0x2ee87a, emissiveIntensity: 2 });
  const sweatMat = new THREE.MeshStandardMaterial({ name: 'sweat', color: 0x8fd8ff, emissive: 0x4fb8ff, emissiveIntensity: 0.6, roughness: 0.1, transparent: true, opacity: 0.9 });
  const screenUI = new THREE.MeshBasicMaterial({ name: 'screen_ui_track', color: 0x1a2330 });
  const screenFill = new THREE.MeshBasicMaterial({ name: 'screen_ui_fill', color: 0x2aa8ff });
  const uiGearMat = new THREE.MeshBasicMaterial({ name: 'screen_ui_gear', color: 0x2aa8ff, side: THREE.DoubleSide });
  const doorMat = shell.clone(); doorMat.name = 'hatch_door'; doorMat.side = THREE.DoubleSide;
  const pops = [];   // objects that scale in/out with maintenance mode

  // Hard hat + rotating beacon
  const helmet = new THREE.Group(); helmet.name = 'helmet'; head.add(helmet); helmet.scale.setScalar(0.0001); helmet.visible = false;
  // Hard-hat shell: domed crown, raised ribs, rolled rim, front peak, safety emblem
  const HB = 0.062, HS = [0.166, 0.108, 0.16];
  add('helmet_shell', new THREE.LatheGeometry([V(1, 0), V(0.99, 0.18), V(0.95, 0.42), V(0.86, 0.64), V(0.7, 0.83), V(0.47, 0.95), V(0.22, 0.995), V(0, 1)], 64),
    hatYellow, { p: [0, HB, 0], s: HS }, helmet);
  add('helmet_rim', new THREE.TorusGeometry(1, 0.04, 10, 72), hatYellow, { p: [0, HB + 0.002, 0], r: [Math.PI / 2, 0, 0], s: [HS[0] + 0.002, HS[2] + 0.002, 0.14] }, helmet);
  add('helmet_peak', new THREE.CylinderGeometry(1, 1, 1, 48, 1, false, -1.0, 2.0), hatYellow, { p: [0, HB + 0.002, 0], r: [0.1, 0, 0], s: [HS[0] + 0.045, 0.006, HS[2] + 0.05] }, helmet);
  for (const rx of [-0.052, 0, 0.052]) {
    const k = Math.sqrt(1 - (rx / HS[0]) ** 2), rib = new THREE.Group(); rib.name = 'helmet_rib'; rib.position.set(rx, HB, 0); rib.rotation.y = Math.PI / 2; helmet.add(rib);
    add('helmet_rib', new THREE.TorusGeometry(1, 0.05, 8, 48, Math.PI), hatYellow, { s: [HS[2] * k + 0.003, HS[1] * k + 0.004, 0.12] }, rib);
  }
  const badgeA = Math.asin(0.045 / HS[1]), badge = new THREE.Group(); badge.name = 'helmet_badge';
  badge.position.set(0.075, HB + 0.045, HS[2] * Math.cos(badgeA) * Math.sqrt(1 - (0.075 / HS[0]) ** 2) + 0.004); badge.rotation.set(-badgeA, 0.5, 0); helmet.add(badge);
  const badgeWhite = new THREE.MeshStandardMaterial({ name: 'badge_white', color: 0xffffff, roughness: 0.5 });
  const badgeGreen = new THREE.MeshStandardMaterial({ name: 'badge_green', color: 0x14a44d, roughness: 0.5 });
  add('badge_disc', new THREE.CircleGeometry(0.017, 32), badgeWhite, {}, badge);
  add('badge_cross_v', new THREE.PlaneGeometry(0.008, 0.024), badgeGreen, { p: [0, 0, 0.0005] }, badge);
  add('badge_cross_h', new THREE.PlaneGeometry(0.024, 0.008), badgeGreen, { p: [0, 0, 0.0005] }, badge);
  add('beacon_base', new THREE.CylinderGeometry(0.018, 0.02, 0.01, 24), stripeBlack, { p: [0, HB + HS[1] + 0.006, -0.02] }, helmet);
  add('beacon_dome', new THREE.SphereGeometry(0.016, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), beaconMat, { p: [0, HB + HS[1] + 0.01, -0.02], s: [1, 1.3, 1] }, helmet);
  // Chin strap + buckle
  const strapMat = new THREE.MeshStandardMaterial({ name: 'strap_black', color: 0x24262b, roughness: 0.7 });
  const strapArc = Math.PI + 2 * Math.asin(HB / 0.153);
  add('chin_strap', new THREE.TorusGeometry(1, 0.05, 8, 64, strapArc), strapMat, { p: [0, 0, 0.022], r: [0, 0, Math.PI - (strapArc - Math.PI) / 2], s: [0.174, 0.153, 0.07] }, helmet);
  add('strap_buckle', new THREE.BoxGeometry(0.016, 0.008, 0.01), stripeBlack, { p: [0, -0.154, 0.022] }, helmet);

  // Display UI: diagnostic gear, 3 check dots, progress bar (bent to the screen curve)
  const bentPlane = (w, hgt) => {
    const g = new THREE.PlaneGeometry(w, hgt, 20, 1), p = g.attributes.position;
    for (let i = 0; i < p.count; i++) p.setZ(i, -(p.getX(i) ** 2) / (2 * hs[0]));
    g.computeVertexNormals(); return g;
  };
  const onScreen = (name, yy) => {
    const g = new THREE.Group(); g.name = name;
    g.position.set(0, yy, hs[2] * 1.012 * Math.sqrt(1 - (yy / (hs[1] * 1.012)) ** 2) + 0.001);
    g.rotation.x = Math.asin(-yy / (hs[1] * 1.012)); head.add(g); return g;
  };
  const ui = onScreen('screen_progress', -0.054);
  add('progress_track', bentPlane(0.06, 0.008), screenUI, { p: [0.012, 0, 0] }, ui).castShadow = false;
  const fillGeo = bentPlane(0.06, 0.008); fillGeo.translate(0.03, 0, 0.0004);
  const fill = add('progress_fill', fillGeo, screenFill, { p: [-0.018, 0, 0] }, ui); fill.castShadow = false;
  const uiGear = new THREE.Group(); uiGear.name = 'screen_gear'; uiGear.position.set(-0.034, 0, -0.003); ui.add(uiGear);
  add('screen_gear_ring', new THREE.RingGeometry(0.0035, 0.0068, 20), uiGearMat, {}, uiGear).castShadow = false;
  for (let i = 0; i < 6; i++) { const an = i / 6 * Math.PI * 2; add('screen_gear_tooth', new THREE.PlaneGeometry(0.0034, 0.0034), uiGearMat, { p: [Math.cos(an) * 0.0078, Math.sin(an) * 0.0078, 0], r: [0, 0, an] }, uiGear).castShadow = false; }
  const ui2 = onScreen('screen_checks', -0.039);
  const checks = [-1, 0, 1].map(i => { const m = add('check_dot', new THREE.CircleGeometry(0.0042, 20), new THREE.MeshBasicMaterial({ name: 'check_dot', color: 0x2a3442 }), { p: [i * 0.018, 0, -((i * 0.018) ** 2) / (2 * hs[0])] }, ui2); m.castShadow = false; return m; });

  // Surprise "O" eyes
  eyes.forEach(e => { const r = add(e.name + '_surprise', new THREE.TorusGeometry(0.017, 0.006, 12, 32), eye, { s: [1, 1.1, 0.3] }, e); r.visible = false; e.userData.surprise = r; });

  // Open service hatch on the belly
  const hy0 = 0.17, hr = 0.162, hatch = new THREE.Group(); hatch.name = 'service_hatch'; hatch.position.set(0, hy0, 0); hatch.rotation.x = 0.25; robot.add(hatch);
  const bentBody = (w, hh) => { const g = new THREE.PlaneGeometry(w, hh, 16, 1), p = g.attributes.position; for (let i = 0; i < p.count; i++) p.setZ(i, Math.sqrt(hr * hr - p.getX(i) ** 2)); g.computeVertexNormals(); return g; };
  const hatchIn = add('hatch_cavity', bentBody(0.07, 0.055), darkMetal, { p: [0, 0, 0.0015] }, hatch); hatchIn.castShadow = false;
  const hatchLeds = [-0.022, -0.008, 0.006].map((x, i) => add('hatch_led', new THREE.SphereGeometry(0.0035, 12, 8), hatchLed.clone(), { p: [x, 0.012, Math.sqrt(hr * hr - x * x) + 0.003] }, hatch));
  add('hatch_chip', new THREE.BoxGeometry(0.024, 0.016, 0.004), housing, { p: [0.014, -0.01, Math.sqrt(hr * hr - 0.014 ** 2) + 0.002] }, hatch);
  const doorPivot = new THREE.Group(); doorPivot.name = 'hatch_hinge'; doorPivot.position.set(-0.035, 0, Math.sqrt(hr * hr - 0.035 ** 2) + 0.003); hatch.add(doorPivot);
  const doorGeo = bentBody(0.07, 0.055); doorGeo.translate(0.035, 0, -Math.sqrt(hr * hr - 0.035 ** 2));
  add('hatch_door', doorGeo, doorMat, {}, doorPivot);
  hatch.visible = false;

  // Tools held in the hands (children of the shoulder pivots)
  const toolTips = [];
  const mkGroup = (name, parent, s) => { const g = new THREE.Group(); g.name = name; g.position.set(-0.035 * s, -0.2, 0); parent.add(g); return g; };
  const L = arms[0], Rt = arms[1];
  const screwdriver = mkGroup('screwdriver', L, -1);
  add('screwdriver_grip', new THREE.CylinderGeometry(0.011, 0.012, 0.045, 20), grip, { p: [0, -0.025, 0] }, screwdriver);
  add('screwdriver_shaft', new THREE.CylinderGeometry(0.0032, 0.0032, 0.06, 12), metal, { p: [0, -0.077, 0] }, screwdriver);
  const wrench = mkGroup('wrench', Rt, 1);
  add('wrench_handle', new THREE.BoxGeometry(0.014, 0.085, 0.006), metal, { p: [0, -0.045, 0] }, wrench);
  add('wrench_head', new THREE.TorusGeometry(0.015, 0.0055, 10, 28, Math.PI * 1.5), metal, { p: [0, -0.097, 0], r: [0, 0, -Math.PI / 4] }, wrench);
  const hammer = mkGroup('hammer', Rt, 1);
  add('hammer_handle', new THREE.CylinderGeometry(0.006, 0.007, 0.09, 12), wood, { p: [0, -0.045, 0] }, hammer);
  add('hammer_head', new THREE.BoxGeometry(0.05, 0.02, 0.02), metal, { p: [0.0, -0.095, 0] }, hammer);
  for (const [g, y] of [[screwdriver, -0.105], [wrench, -0.1]]) { const tp = new THREE.Object3D(); tp.position.y = y; g.add(tp); toolTips.push(tp); }
  [screwdriver, wrench, hammer].forEach(g => g.scale.setScalar(0.0001));

  // Work pose + floating module placed where the tool tips meet
  const workPose = (a, s, k) => { a.rotation.x = -1.3 * k; a.rotation.z = s * -0.25 * k; };
  arms.forEach(a => workPose(a, a.userData.sx, 1)); screwdriver.scale.setScalar(1); wrench.scale.setScalar(1);
  robot.updateMatrixWorld(true);
  const tipPos = toolTips.map(t => robot.worldToLocal(t.getWorldPosition(new THREE.Vector3())));
  arms.forEach(a => workPose(a, a.userData.sx, 0)); screwdriver.scale.setScalar(0.0001); wrench.scale.setScalar(0.0001);
  const modW = Math.abs(tipPos[1].x - tipPos[0].x) - 0.012;
  const modC = new THREE.Vector3(0, (tipPos[0].y + tipPos[1].y) / 2, (tipPos[0].z + tipPos[1].z) / 2);
  const module = new THREE.Group(); module.name = 'repair_module'; module.position.copy(modC); robot.add(module); pops.push(module);
  add('module_housing', new THREE.BoxGeometry(modW, 0.06, 0.07), housing, {}, module);
  add('module_front', new THREE.BoxGeometry(modW * 0.78, 0.04, 0.004), darkMetal, { p: [0, -0.002, 0.0352] }, module);
  for (const s of [-1, 1]) add('module_bolt', new THREE.CylinderGeometry(0.008, 0.008, 0.006, 6), metal, { p: [s * (modW / 2 + 0.002), 0, 0], r: [0, 0, Math.PI / 2] }, module);
  add('module_led', new THREE.SphereGeometry(0.006, 16, 12), ledMat, { p: [modW * 0.3, 0.008, 0.038] }, module);
  const gear = new THREE.Group(); gear.name = 'gear'; gear.position.y = 0.036; module.add(gear);
  add('gear_disc', new THREE.CylinderGeometry(0.022, 0.022, 0.008, 24), metal, {}, gear);
  for (let i = 0; i < 10; i++) { const an = i / 10 * Math.PI * 2; add('gear_tooth', new THREE.BoxGeometry(0.008, 0.008, 0.008), metal, { p: [Math.cos(an) * 0.025, 0, Math.sin(an) * 0.025], r: [0, -an, 0] }, gear); }

  // Floor: striped safety ring + open toolbox (in root, so they stay put)
  const floor = new THREE.Group(); floor.name = 'safety_zone'; floor.position.y = groundY + 0.001; root.add(floor); pops.push(floor);
  for (let i = 0; i < 36; i++) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.44, 0.48, 3, 1, i / 36 * Math.PI * 2, Math.PI * 2 / 36), i % 2 ? stripeBlack : hatYellow);
    m.name = 'stripe'; m.rotation.x = -Math.PI / 2; m.receiveShadow = true; floor.add(m);
  }
  const toolbox = new THREE.Group(); toolbox.name = 'toolbox'; toolbox.position.set(0.33, groundY, 0.07); toolbox.rotation.y = -0.4; root.add(toolbox); pops.push(toolbox);
  const tb = (n, g, m, c) => { const o = add(n, g, m, c, toolbox); o.receiveShadow = true; return o; };
  tb('toolbox_body', new THREE.BoxGeometry(0.13, 0.055, 0.07), boxRed, { p: [0, 0.0275, 0] });
  tb('toolbox_inside', new THREE.BoxGeometry(0.122, 0.002, 0.062), stripeBlack, { p: [0, 0.054, 0] });
  const lid = new THREE.Group(); lid.name = 'toolbox_lid_hinge'; lid.position.set(0, 0.055, -0.035); lid.rotation.x = -1.9; toolbox.add(lid);
  add('toolbox_lid', new THREE.BoxGeometry(0.13, 0.006, 0.07), boxRed, { p: [0, 0.003, 0.035] }, lid);
  tb('toolbox_tool_1', new THREE.CylinderGeometry(0.006, 0.006, 0.06, 10), grip, { p: [-0.03, 0.06, 0.01], r: [0.3, 0, 0.5] });
  tb('toolbox_tool_2', new THREE.BoxGeometry(0.01, 0.06, 0.004), metal, { p: [0.0, 0.065, -0.005], r: [0.2, 0, -0.3] });
  tb('toolbox_tool_3', new THREE.CylinderGeometry(0.005, 0.005, 0.055, 10), wood, { p: [0.03, 0.062, 0.0], r: [-0.2, 0, 0.2] });

  // Safety vest bands on the body
  const radAt = yy => { for (let i = 1; i < bodyPts.length; i++) { const a = bodyPts[i - 1], b = bodyPts[i]; if (yy <= b.y) return a.x + (b.x - a.x) * (yy - a.y) / (b.y - a.y); } return 0; };
  const vestMat = new THREE.MeshStandardMaterial({ name: 'vest_orange', color: 0xff6a00, emissive: 0xff5a00, emissiveIntensity: 0.35, roughness: 0.5 });
  const reflectMat = new THREE.MeshStandardMaterial({ name: 'vest_reflective', color: 0xeef1f4, emissive: 0xaab0b8, emissiveIntensity: 0.5, roughness: 0.2, metalness: 0.3 });
  const vest = new THREE.Group(); vest.name = 'safety_vest'; vest.visible = false; robot.add(vest);
  for (const [y1, y2] of [[0.092, 0.128], [0.212, 0.248]]) {
    const ym = (y1 + y2) / 2;
    add('vest_band', new THREE.CylinderGeometry(radAt(y2) + 0.0025, radAt(y1) + 0.0025, y2 - y1, 72, 1, true), vestMat, { p: [0, ym, 0] }, vest);
    add('vest_reflective', new THREE.CylinderGeometry(radAt(ym + 0.004) + 0.0038, radAt(ym - 0.004) + 0.0038, 0.008, 72, 1, true), reflectMat, { p: [0, ym, 0] }, vest);
  }

  // Traffic cones around the safety ring
  const coneMat = new THREE.MeshStandardMaterial({ name: 'cone_orange', color: 0xff5a14, roughness: 0.45 });
  for (const an of [1.0, 2.4, 3.9, 5.3]) {
    const c = new THREE.Group(); c.name = 'traffic_cone'; c.position.set(Math.cos(an) * 0.52, 0, Math.sin(an) * 0.52); floor.add(c);
    add('cone_base', new THREE.BoxGeometry(0.058, 0.006, 0.058), stripeBlack, { p: [0, 0.003, 0] }, c);
    add('cone_body', new THREE.CylinderGeometry(0.004, 0.024, 0.085, 32), coneMat, { p: [0, 0.0485, 0] }, c);
    add('cone_band', new THREE.CylinderGeometry(0.0136, 0.0168, 0.014, 32, 1, true), reflectMat, { p: [0, 0.047, 0] }, c);
  }

  // Speech bubble (camera-facing sprite drawn on a canvas)
  const bubbleCanvas = document.createElement('canvas'); bubbleCanvas.width = 512; bubbleCanvas.height = 200;
  const bctx = bubbleCanvas.getContext('2d');
  const bubbleTex = new THREE.CanvasTexture(bubbleCanvas); bubbleTex.colorSpace = THREE.SRGBColorSpace;
  const bubble = new THREE.Sprite(new THREE.SpriteMaterial({ map: bubbleTex, depthTest: false, transparent: true }));
  bubble.name = 'speech_bubble'; bubble.renderOrder = 10; bubble.center.set(1, 0); bubble.visible = false; root.add(bubble);
  const drawBubble = text => {
    bctx.clearRect(0, 0, 512, 200);
    bctx.fillStyle = '#ffffff'; bctx.strokeStyle = '#1d1f23'; bctx.lineWidth = 7;
    bctx.beginPath(); bctx.roundRect(12, 12, 488, 130, 48); bctx.fill(); bctx.stroke();
    bctx.beginPath(); bctx.moveTo(400, 138); bctx.lineTo(470, 190); bctx.lineTo(450, 138); bctx.closePath(); bctx.fill();
    bctx.beginPath(); bctx.moveTo(400, 142); bctx.lineTo(470, 190); bctx.lineTo(450, 142); bctx.stroke();
    bctx.fillStyle = '#ffffff'; bctx.fillRect(396, 128, 58, 12);
    bctx.fillStyle = '#1d1f23'; bctx.font = '700 54px system-ui, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif';
    bctx.textAlign = 'center'; bctx.textBaseline = 'middle'; bctx.fillText(text, 256, 79);
    bubbleTex.needsUpdate = true;
  };
  let lastBubble = '', bubbleBorn = 0, doneBurst = false;

  // Smoke puffs
  const smoke = Array.from({ length: 14 }, () => { const m = add('smoke', new THREE.SphereGeometry(0.012, 12, 8), new THREE.MeshBasicMaterial({ name: 'smoke', color: 0x9aa0a6, transparent: true, opacity: 0, depthWrite: false })); m.castShadow = false; m.visible = false; m.userData = { v: new THREE.Vector3(), life: 0 }; return m; });
  const emitSmoke = (at, n) => { let k = 0; for (const s of smoke) { if (s.userData.life > 0) continue; s.position.copy(at).add(new THREE.Vector3((Math.random() - 0.5) * 0.02, 0, (Math.random() - 0.5) * 0.02)); s.userData.v.set((Math.random() - 0.5) * 0.04, 0.07 + Math.random() * 0.04, (Math.random() - 0.5) * 0.04); s.userData.life = 1.2; s.visible = true; if (++k >= n) break; } };

  // Done: green check mark + confetti
  const okMat = new THREE.MeshStandardMaterial({ name: 'check_green', color: 0x2ee87a, emissive: 0x1fd068, emissiveIntensity: 1.4, roughness: 0.4 });
  const check = new THREE.Group(); check.name = 'done_check'; check.visible = false; root.add(check);
  for (const [x1, y1, x2, y2] of [[-0.034, 0.002, -0.01, -0.022], [-0.01, -0.022, 0.036, 0.03]]) {
    const dx = x2 - x1, dy = y2 - y1;
    add('check_stroke', new THREE.CapsuleGeometry(0.008, Math.hypot(dx, dy), 6, 16), okMat, { p: [(x1 + x2) / 2, (y1 + y2) / 2, 0], r: [0, 0, Math.atan2(-dx, dy)] }, check);
  }
  const confColors = [0xff4d6d, 0xffc21a, 0x2ee87a, 0x2aa8ff, 0xb46cff];
  const confetti = Array.from({ length: 36 }, (_, i) => { const m = add('confetti', new THREE.BoxGeometry(0.009, 0.009, 0.002), new THREE.MeshBasicMaterial({ name: 'confetti', color: confColors[i % 5], transparent: true })); m.castShadow = false; m.visible = false; m.userData = { v: new THREE.Vector3(), w: new THREE.Vector3(), life: 0 }; return m; });
  const burstConfetti = at => confetti.forEach(c => { c.position.copy(at); const a = Math.random() * Math.PI * 2, sp = 0.25 + Math.random() * 0.35; c.userData.v.set(Math.cos(a) * sp, 0.5 + Math.random() * 0.5, Math.sin(a) * sp); c.userData.w.set(Math.random() * 20, Math.random() * 20, Math.random() * 20); c.userData.life = 1.5; c.visible = true; });
  const easeBack = k => { const c = 1.9; return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2; };
  const bounceOut = k => { const n = 7.5625, d = 2.75; if (k < 1 / d) return n * k * k; if (k < 2 / d) return n * (k -= 1.5 / d) * k + 0.75; if (k < 2.5 / d) return n * (k -= 2.25 / d) * k + 0.9375; return n * (k -= 2.625 / d) * k + 0.984375; };

  // Flying screw + sweat drop
  const screw = new THREE.Group(); screw.name = 'loose_screw'; screw.visible = false; root.add(screw);
  add('screw_shaft', new THREE.CylinderGeometry(0.003, 0.003, 0.018, 10), metal, { p: [0, -0.009, 0] }, screw);
  add('screw_head', new THREE.CylinderGeometry(0.0075, 0.0075, 0.004, 16), metal, {}, screw);
  const screwV = new THREE.Vector3(); let screwLive = false;
  const sweat = add('sweat_drop', new THREE.SphereGeometry(0.008, 16, 12), sweatMat, { s: [1, 1.5, 1] }); sweat.visible = false; sweat.castShadow = false;

  // Sparks
  const sparkMat = new THREE.MeshBasicMaterial({ name: 'spark', color: 0xffc040, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
  const sparks = Array.from({ length: 24 }, () => { const m = add('spark', new THREE.SphereGeometry(0.0035, 8, 6), sparkMat.clone()); m.castShadow = false; m.visible = false; m.userData = { v: new THREE.Vector3(), life: 0 }; return m; });
  const emitSparks = (at, n, power = 1) => { let k = 0; for (const s of sparks) { if (s.userData.life > 0) continue; s.position.copy(at); s.userData.v.set((Math.random() - 0.3) * 0.6 * power, (Math.random() * 0.6 + 0.2) * power, (Math.random() - 0.2) * 0.5 * power); s.userData.life = 0.35 + Math.random() * 0.25; s.visible = true; if (++k >= n) break; } };
  pops.forEach(o => o.scale.setScalar(0.0001));

  // ---------- Face icons: the display itself shows status ----------
  const mkIcon = draw => { const c = document.createElement('canvas'); c.width = 256; c.height = 128; const x = c.getContext('2d'); draw(x); const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace; return tx; };
  const iconTex = {
    warn: mkIcon(x => { x.strokeStyle = x.fillStyle = '#ffc21a'; x.lineWidth = 12; x.lineJoin = 'round'; x.beginPath(); x.moveTo(128, 14); x.lineTo(186, 114); x.lineTo(70, 114); x.closePath(); x.stroke(); x.fillRect(122, 46, 12, 40); x.beginPath(); x.arc(128, 100, 7, 0, Math.PI * 2); x.fill(); }),
    err: mkIcon(x => { x.fillStyle = '#ff3030'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.font = '800 78px system-ui, sans-serif'; x.fillText('E-07', 128, 54); x.font = '700 24px system-ui, sans-serif'; x.fillText('MOTOR OVERHEAT', 128, 108); }),
    check: mkIcon(x => { x.strokeStyle = '#2ee87a'; x.lineWidth = 16; x.lineCap = x.lineJoin = 'round'; x.beginPath(); x.moveTo(88, 66); x.lineTo(116, 94); x.lineTo(170, 36); x.stroke(); }),
  };
  const iconMat = new THREE.MeshBasicMaterial({ name: 'screen_icon', map: iconTex.warn, transparent: true, depthWrite: false });
  const iconPlane = add('screen_icon', bentPlane(0.12, 0.06), iconMat, {}, onScreen('screen_icon_mount', -0.004));
  iconPlane.castShadow = false; iconPlane.visible = false;

  // ---------- X-ray internals (revealed in fault mode) ----------
  bodyMat.transparent = true; bodyMat.needsUpdate = true;
  const inner = new THREE.Group(); inner.name = 'internals'; inner.visible = false; robot.add(inner);
  const pcb = new THREE.MeshStandardMaterial({ name: 'pcb_green', color: 0x1f7a4a, roughness: 0.6 });
  const copper = new THREE.MeshStandardMaterial({ name: 'copper', color: 0xd07a3a, roughness: 0.35, metalness: 0.35 });
  const battMat = new THREE.MeshStandardMaterial({ name: 'battery', color: 0x3b4652, roughness: 0.5 });
  const battBand = new THREE.MeshStandardMaterial({ name: 'battery_band', color: 0x2ee87a, emissive: 0x1fd068, emissiveIntensity: 0.8 });
  const motorMat = new THREE.MeshStandardMaterial({ name: 'motor_housing', color: 0x5a6470, roughness: 0.4, metalness: 0.3, emissive: 0xff0000, emissiveIntensity: 0 });
  add('battery', new THREE.BoxGeometry(0.1, 0.07, 0.07), battMat, { p: [0, 0.12, 0] }, inner);
  add('battery_band', new THREE.BoxGeometry(0.102, 0.012, 0.072), battBand, { p: [0, 0.135, 0] }, inner);
  for (const s of [-1, 1]) add('battery_terminal', new THREE.CylinderGeometry(0.007, 0.007, 0.01, 12), metal, { p: [s * 0.03, 0.16, 0] }, inner);
  const motor = new THREE.Group(); motor.name = 'motor'; motor.position.set(0, 0.29, 0); inner.add(motor);
  add('motor_housing', new THREE.CylinderGeometry(0.045, 0.045, 0.07, 32), motorMat, { r: [0, 0, Math.PI / 2] }, motor);
  for (const x of [-0.022, 0, 0.022]) add('motor_coil', new THREE.TorusGeometry(0.047, 0.005, 8, 32), copper, { p: [x, 0, 0], r: [0, Math.PI / 2, 0] }, motor);
  add('motor_shaft', new THREE.CylinderGeometry(0.006, 0.006, 0.13, 12), metal, { r: [0, 0, Math.PI / 2] }, motor);
  const heat = add('motor_heat', new THREE.SphereGeometry(0.075, 24, 16), new THREE.MeshBasicMaterial({ name: 'motor_heat', color: 0xff2020, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }), {}, motor);
  heat.castShadow = false;
  const innerGears = [-1, 1].map(s => { const g = new THREE.Group(); g.name = 'drive_gear'; g.position.set(s * 0.075, 0.21, 0); inner.add(g);
    add('drive_gear_disc', new THREE.CylinderGeometry(0.026, 0.026, 0.01, 24), metal, { r: [Math.PI / 2, 0, 0] }, g);
    for (let i = 0; i < 10; i++) { const an = i / 10 * Math.PI * 2; add('drive_gear_tooth', new THREE.BoxGeometry(0.008, 0.008, 0.01), metal, { p: [Math.cos(an) * 0.029, Math.sin(an) * 0.029, 0], r: [0, 0, an] }, g); }
    return g; });
  const cpu = new THREE.Group(); cpu.name = 'head_internals'; cpu.visible = false; head.add(cpu);
  add('cpu_board', new THREE.BoxGeometry(0.08, 0.006, 0.07), pcb, { p: [0, -0.05, -0.03] }, cpu);
  add('cpu_chip', new THREE.BoxGeometry(0.028, 0.006, 0.028), darkMetal, { p: [0, -0.044, -0.03] }, cpu);
  for (const [col, xo] of [[0xff4040, 0.02], [0x3a8bff, -0.02]]) {
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(xo, 0.16, 0.02), new THREE.Vector3(xo * 2.5, 0.2, 0.05), new THREE.Vector3(xo * 1.5, 0.25, 0.04), new THREE.Vector3(xo, 0.27, 0.02)]);
    add('wire', new THREE.TubeGeometry(curve, 24, 0.0035, 8), new THREE.MeshStandardMaterial({ name: 'wire', color: col, roughness: 0.5 }), {}, inner);
  }
  // ---------- Status glow on the floor ----------
  const glowCanvas = document.createElement('canvas'); glowCanvas.width = glowCanvas.height = 256;
  { const x = glowCanvas.getContext('2d'), g = x.createRadialGradient(128, 128, 0, 128, 128, 128); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.45, 'rgba(255,255,255,.45)'); g.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = g; x.fillRect(0, 0, 256, 256); }
  const floorGlowMat = new THREE.MeshBasicMaterial({ name: 'status_glow', map: new THREE.CanvasTexture(glowCanvas), color: 0x2ee87a, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false });
  const floorGlow = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.9), floorGlowMat); floorGlow.name = 'status_glow'; floorGlow.rotation.x = -Math.PI / 2; floorGlow.position.y = groundY + 0.003; root.add(floorGlow);
  const STATUS = [0x2ee87a, 0xffb800, 0xff2020, 0x3a8bff].map(c => new THREE.Color(c));
  let xray = 0;

  // ---------- Stages: 0 normal · 1 caution · 2 fault · 3 maintenance ----------
  let mode = 0, modeT = 0;
  const blushes = head.children.filter(c => c.name.startsWith('blush'));
  const seamMesh = robot.getObjectByName('body_seam');
  const seamAlert = new THREE.MeshStandardMaterial({ name: 'seam_alert', color: 0xff3030, emissive: 0xff1a1a, emissiveIntensity: 2 });
  const C = { blue: new THREE.Color(0x2aa8ff), yellow: new THREE.Color(0xffb800), red: new THREE.Color(0xff2a2a), amber: new THREE.Color(0xff9a00), deep: new THREE.Color(0xf20505), green: new THREE.Color(0x2ee87a), orange: new THREE.Color(0xff8a1a), dim: new THREE.Color(0x2a3442), off: new THREE.Color(0x000000) };
  const setEyeShape = shape => eyes.forEach(e => e.children.forEach(c => {
    c.visible = c === e.userData.panic ? shape === 'panic' : c === e.userData.surprise ? shape === 'surprise' : shape === 'arc';
  }));
  let transT = -10, curT = 0;
  const setMode = m => {
    if (m === mode && transT > -10) return;
    mode = m; modeT = 0; transT = curT;
    blushes.forEach(b => b.visible = m === 0);
    eyes.forEach(e => e.rotation.z = m === 1 ? Math.PI : 0);
    setEyeShape(m === 2 ? 'panic' : 'arc');
    sign.visible = m === 1 || m === 2;
    signMat.color.copy(m === 1 ? C.yellow : C.red); signMat.emissive.copy(m === 1 ? C.yellow : C.red);
    seamMesh.material = m === 2 ? seamAlert : seam;
    uTint.value.copy(m === 1 ? C.amber : C.deep);
    ui.visible = ui2.visible = hatch.visible = m === 3;
    screw.visible = false; screwLive = false; sweat.visible = false;
    bubble.visible = check.visible = false; lastBubble = ''; doneBurst = false;
    robot.rotation.y %= Math.PI * 2;
  };
  setMode(0);

  // Maintenance timeline (seconds within a 12s loop)
  const CYCLE = 12, T_DONE = 10.4;
  const PH = [['work', 0, 3.5], ['wipe', 3.5, 4.8], ['fetch', 4.8, 6.0], ['hammer', 6.0, 7.4], ['startle', 7.4, 8.6], ['hammer', 8.6, T_DONE], ['done', T_DONE, CYCLE]];
  const phaseAt = T => PH.find(p => T >= p[1] && T < p[2]) || PH[0];
  const hammerSwing = t => { const k = (t * 2.5) % 1; return k < 0.75 ? Math.sin(k / 0.75 * Math.PI / 2) : 1 - (k - 0.75) / 0.25; };

  // Normal idle timeline (14s loop): float → look around → wave → happy hop
  const NC = 14, NPH = [['float', 0, 5], ['look', 5, 7.5], ['wave', 7.5, 10], ['hop', 10, 11.2], ['float', 11.2, NC]];
  const nPhaseAt = T => NPH.find(p => T >= p[1] && T < p[2]) || NPH[0];

  const strobeNow = t => Math.sin(t * 14) > 0;
  const ease = (cur, target, k, dt) => cur + (target - cur) * Math.min(1, dt * k);
  let armLift = 0, maint = 0, sparkClock = 0, prevSwing = 0, prevT = 0;
  const armCur = arms.map(() => ({ x: 0, z: 0 })), headCur = { x: 0, y: 0, z: 0 };
  const update = (t, dt, camera) => {
    curT = t; modeT += dt;
    uTime.value = t;
    uAlert.value = ease(uAlert.value, [0, 0.45, 1, 0][mode], 5, dt);
    armLift = ease(armLift, mode === 2 ? 1 : 0, 8, dt);
    maint = ease(maint, mode === 3 ? 1 : 0, 6, dt);
    const T = modeT % CYCLE, ph = mode === 3 ? phaseAt(T)[0] : null, phT = mode === 3 ? T - phaseAt(T)[1] : 0;
    const wrapped = T < prevT; prevT = T;
    const NT = modeT % NC, nph = mode === 0 ? nPhaseAt(NT)[0] : null, nT = mode === 0 ? NT - nPhaseAt(NT)[1] : 0;
    const tk = t - transT;   // time since last stage change
    if (mode === 3 && wrapped) { screw.visible = false; screwLive = false; doneBurst = false; }

    // ----- body -----
    let y = baseY + Math.sin(t * 1.6) * 0.012, air = 0;
    let sx = 1, sy = 1, px = 0, rz = 0;
    if (mode === 1) { px = Math.sin(t * 40) * 0.002; rz = Math.sin(t * 27) * 0.012; }
    if (nph === 'hop') y += Math.abs(Math.sin(nT / 1.2 * Math.PI * 2)) * 0.05;
    if (nph === 'wave') rz = Math.sin(t * 6) * 0.02;
    const swing = hammerSwing(t), impact = ph === 'hammer' && prevSwing > 0.6 && swing < prevSwing && swing < 0.05; prevSwing = swing;
    if (mode === 3) {
      y = baseY + Math.sin(t * 1.2) * 0.005;
      if (ph === 'work') rz = Math.sin(t * 6) * 0.012;
      if (ph === 'hammer') rz = -swing * 0.02;
      if (ph === 'startle') y += Math.max(0, Math.sin(Math.min(1, phT / 0.25) * Math.PI)) * 0.04;
      if (ph === 'done') y += Math.abs(Math.sin(phT * 6)) * 0.035 * Math.max(0, 1 - phT / 1.6);
    }
    if (mode === 2) {
      const q = (t * 3.2) % 1; air = Math.sin(q * Math.PI);
      y = baseY + air * 0.14;
      const land = Math.max(0, 1 - air * 6);
      sx = 1 + land * 0.1; sy = 1 - land * 0.14 + air * 0.05;
      px = Math.sin(t * 47) * 0.007; rz = Math.sin(t * 31) * 0.06;
      robot.rotation.y += dt * 4.5;
    } else {
      const r = robot.rotation.y, target = Math.round(r / (Math.PI * 2)) * Math.PI * 2;
      robot.rotation.y = ease(r, target, 4, dt);
    }
    if (tk < 0.6) { const sq = 0.13 * Math.exp(-7 * tk) * Math.cos(18 * tk); sy *= 1 - sq; sx *= 1 + sq * 0.6; }
    robot.position.set(px, y, 0); robot.rotation.z = rz; robot.scale.set(sx, sy, sx);
    uBase.value = y;

    // ----- arms (eased toward per-phase targets) -----
    arms.forEach((a, i) => {
      const s = a.userData.sx, right = s > 0;
      let tx = 0, tz = s * armLift * (2.3 + Math.sin(t * 16 + i * Math.PI) * 0.55), k = mode === 2 ? 30 : 9;
      if (nph === 'wave') { if (right) { tx = -0.25; tz = 2.45 + Math.sin(t * 12) * 0.35; } else { tz = -0.12; } k = 10; }
      if (nph === 'hop') { tx = -0.2; tz = s * 0.6; k = 10; }
      if (mode === 3) {
        k = 9; tx = -1.3; tz = -0.25;
        if (ph === 'work') { if (right) { tx += Math.sin(t * 6) * 0.1; tz += Math.sin(t * 6 + 1) * 0.07; } else { tx += Math.sin(t * 3.2) * 0.04; tz += Math.sin(t * 9) * 0.015; } }
        if (ph === 'wipe' && right) { tx = 0.43; tz = -2.72 + Math.sin(t * 10) * 0.18; k = 7; }
        if (ph === 'fetch') { if (right) { tx = -0.3; tz = 0.5; k = 7; } else { tx = -1.0; tz = -0.15; } }
        if (ph === 'hammer' && right) { tx = -1.3 - swing * 0.6; k = 28; }
        if (ph === 'startle') { tx = -0.5; tz = 0.75 + Math.sin(t * 20) * 0.05; k = 14; }
        if (ph === 'done') { tx = -0.2; tz = 2.3 + Math.sin(t * 10 + i * Math.PI) * 0.3; k = 10; }
        tz *= s;
      }
      armCur[i].x = ease(armCur[i].x, tx, k, dt); armCur[i].z = ease(armCur[i].z, tz, k, dt);
      a.rotation.x = armCur[i].x; a.rotation.z = armCur[i].z;
    });
    // tools: wrench before the toolbox swap and after the finish, hammer in between
    const useHammer = mode === 3 && T >= 5.4 && T < 11.2;
    const pop = v => Math.max(0.0001, Math.min(1, v));
    screwdriver.scale.setScalar(pop(maint * 1.15));
    wrench.scale.setScalar(pop(mode === 3 && !useHammer ? maint * 1.15 : wrench.scale.x - dt * 8));
    hammer.scale.setScalar(pop(useHammer ? hammer.scale.x + dt * 8 : hammer.scale.x - dt * 8));
    wrench.rotation.y = ph === 'work' ? Math.sin(t * 6) * 0.6 : 0;
    if (ph === 'work') screwdriver.rotation.y += dt * 14;
    pops.forEach(o => o.scale.setScalar(pop(maint * 1.15)));
    // helmet drops onto the head on entry, lifts off on exit
    if (mode === 3) { helmet.visible = true; helmet.scale.setScalar(1); helmet.position.y = 0.32 * (1 - bounceOut(Math.min(1, modeT / 0.75))); }
    else { helmet.visible = maint > 0.01; helmet.scale.setScalar(pop(maint * 1.1)); helmet.position.y = (1 - maint) * 0.25; }
    vest.visible = maint > 0.01; { const vs = 0.9 + 0.1 * maint; vest.scale.set(vs, 1, vs); }
    doorPivot.rotation.y = -1.9 * maint;
    module.position.y = modC.y + (ph === 'work' ? Math.sin(t * 6) * 0.002 : impact ? -0.004 : 0);
    gear.rotation.y += dt * (ph === 'work' || ph === 'hammer' ? 5 : ph === 'done' ? 1 : 0);

    // ----- head -----
    if (mode === 2) { head.position.y = hy + (1 - air) * 0.012; head.rotation.set(0, Math.sin(t * 6) * 0.35, Math.sin(t * 23) * 0.12); }
    else if (mode === 1) { head.position.y = hy; head.rotation.set(0, Math.sin(t * 2.2) * 0.25, Math.sin(t * 5) * 0.03); }
    else {
      let hx = 0, hyaw = Math.sin(t * 0.45) * 0.12, hz = Math.sin(t * 0.7) * 0.07, k = 6;
      head.position.y = hy + (mode === 0 ? Math.sin(t * 1.6 - 0.6) * 0.005 : 0);
      if (nph === 'look') { hx = -0.05; hyaw = Math.sin(nT / 2.5 * Math.PI * 2) * 0.65; hz = 0; k = 5; }
      if (nph === 'wave') { hx = -0.08; hyaw = 0.12; hz = 0.16; k = 7; }
      if (nph === 'hop') { hx = -0.1; hyaw = 0; hz = Math.sin(nT * 10) * 0.08; k = 9; }
      if (mode === 3) {
        k = 7;
        if (ph === 'work') { hx = 0.32 + Math.sin(t * 1.3) * 0.04; hyaw = Math.sin(t * 0.9) * 0.18; hz = Math.sin(t * 1.7) * 0.06; }
        if (ph === 'wipe') { hx = -0.12; hyaw = -0.15; hz = -0.14; }
        if (ph === 'fetch') { hx = 0.45; hyaw = 0.7; hz = 0.1; }
        if (ph === 'hammer') { hx = 0.3 + swing * 0.05; hyaw = 0.05; hz = 0; k = 12; }
        if (ph === 'startle' && screw.visible) { const sp = screw.position; hyaw = Math.min(1.1, Math.atan2(sp.x, Math.max(0.05, sp.z))); hx = Math.max(-0.3, Math.min(0.55, -(sp.y - (y + hy)) * 1.6)); hz = 0; k = 14; }
        if (ph === 'done') { hx = 0.05; hyaw = 0; hz = Math.sin(phT * 7) * 0.13; k = 10; }
      }
      headCur.x = ease(headCur.x, hx, k, dt); headCur.y = ease(headCur.y, hyaw, k, dt); headCur.z = ease(headCur.z, hz, k, dt);
      head.rotation.set(headCur.x, headCur.y, headCur.z);
    }

    // ----- eyes -----
    let eyeCol = C.blue, eyeK = 2.4, blinkS = 1;
    const blink = q => q < 0.16 ? Math.max(0.12, Math.abs(Math.cos(q / 0.16 * Math.PI))) : 1;
    if (mode === 0) blinkS = nph === 'wave' || nph === 'hop' ? 1 : blink(t % 4.2);
    if (mode === 1) { eyeCol = C.yellow; eyeK = 1.6 + Math.sin(t * 6) * 0.8; }
    if (mode === 2) { eyeCol = C.red; eyeK = Math.sin(t * 14) > 0 ? 2.6 : 0.3; }
    if (mode === 3) {
      setEyeShape(ph === 'startle' && phT < 0.9 ? 'surprise' : 'arc');
      blinkS = ph === 'work' || ph === 'hammer' ? 0.38 * blink(t % 3.1) : ph === 'wipe' ? 0.7 : 1;
    }
    eye.color.copy(eyeK > 0.05 ? eyeCol : C.off); eye.emissive.copy(eyeCol).multiplyScalar(eyeK / 2.4);
    glow.color.copy(eyeCol); glow.opacity = 0.22 * Math.min(1, eyeK / 2.4);
    if (tk < 0.18) blinkS = Math.min(blinkS, 0.12);
    eyes.forEach(e => { e.scale.y = blinkS; e.scale.x = 1; });
    seamAlert.emissiveIntensity = Math.sin(t * 14) > 0 ? 2.5 : 0.4;

    // ----- maintenance details -----
    const prog = Math.min(1, T / T_DONE), done = ph === 'done';
    fill.scale.x = Math.max(0.0001, prog);
    screenFill.color.copy(done ? C.green : C.blue);
    uiGearMat.color.copy(done ? C.green : C.blue);
    if (mode === 3 && !done) uiGear.rotation.z -= dt * 3;
    checks.forEach((c, i) => c.material.color.copy(prog >= (i + 1) / 3 ? C.green : C.dim));
    const ledCol = done ? C.green : (Math.sin(t * 10) > 0 ? C.red : C.orange);
    ledMat.color.copy(ledCol); ledMat.emissive.copy(ledCol);
    ledMat.emissiveIntensity = mode === 3 ? (done ? 2.2 : 1.4 + Math.sin(t * 10) * 0.8) : 0.3;
    hatchLeds.forEach((m, i) => { const on = Math.sin(t * (5 + i * 2.3) + i) > 0; const c = done ? C.green : i === 1 ? C.red : C.green; m.material.color.copy(c); m.material.emissive.copy(c); m.material.emissiveIntensity = on ? 2.2 : 0.2; });
    // beacon
    beaconMat.emissiveIntensity = 1.2 + Math.max(0, Math.sin(t * 8)) * 2;
    // sparks
    sparkClock -= dt;
    const sparkAt = new THREE.Vector3(modC.x + modW / 2 + 0.004, modC.y + 0.005, modC.z + 0.01);
    if (ph === 'work' && maint > 0.9 && sparkClock <= 0) { sparkClock = 0.25 + Math.random() * 0.3; emitSparks(sparkAt, 3 + (Math.random() * 3 | 0)); }
    if (impact) { emitSparks(sparkAt.clone().add(new THREE.Vector3(0, 0.02, 0)), 7, 1.4); emitSmoke(new THREE.Vector3(modC.x + modW * 0.3, modC.y + 0.035, modC.z), 2); }
    for (const s of smoke) {
      const u = s.userData; if (u.life <= 0) continue;
      u.life -= dt; s.position.addScaledVector(u.v, dt);
      s.scale.setScalar(1 + (1.2 - u.life) * 2.2); s.material.opacity = Math.max(0, u.life / 1.2) * 0.45; s.visible = u.life > 0;
    }
    for (const s of sparks) {
      const u = s.userData; if (u.life <= 0) continue;
      u.life -= dt; u.v.y -= 2.2 * dt; s.position.addScaledVector(u.v, dt);
      s.material.opacity = Math.max(0, u.life * 2.5); s.visible = u.life > 0;
    }
    // sweat drop during the wipe
    if (ph === 'wipe' && phT < 0.9) {
      sweat.visible = true;
      sweat.position.set(-0.13, hy + 0.06 - phT * phT * 0.35, 0.06);
    } else sweat.visible = false;
    // loose screw pops out at the start of the startle phase
    if (ph === 'startle' && !screwLive && phT < 0.1) {
      screwLive = true; screw.visible = true;
      screw.position.set(modC.x + 0.03, y + modC.y + 0.04, modC.z);
      screwV.set(0.55, 0.9, 0.3);
      emitSmoke(new THREE.Vector3(modC.x + 0.03, modC.y + 0.04, modC.z), 4);
    }
    if (screwLive) {
      screwV.y -= 3.2 * dt; screw.position.addScaledVector(screwV, dt);
      screw.rotation.x += dt * 18 * screwV.length(); screw.rotation.z += dt * 11 * screwV.length();
      if (screw.position.y < groundY + 0.004) { screw.position.y = groundY + 0.004; screwV.y = Math.abs(screwV.y) * 0.35; screwV.x *= 0.6; screwV.z *= 0.6; if (screwV.length() < 0.05) { screwV.set(0, 0, 0); screw.rotation.set(Math.PI / 2, 0, screw.rotation.z); } }
    }
    // brief yellow "!" while startled
    if (mode === 3) {
      const show = ph === 'startle' && phT > 0.05 && phT < 0.9;
      sign.visible = show; signMat.color.copy(C.yellow); signMat.emissive.copy(C.yellow);
    }

    // speech bubble
    const say = mode === 0 ? (nph === 'wave' ? '안녕하세요!' : '') : mode === 1 ? (modeT % 6 < 3 ? '확인이 필요해요' : '점검해 주세요') : mode !== 3 ? '' : ph === 'work' ? '정비 중이에요' : ph === 'wipe' ? '휴~ 덥다' : ph === 'fetch' ? '망치가 필요해' : ph === 'startle' ? '앗, 나사가!' : ph === 'done' ? '수리 완료!' : T < 8.6 ? '쾅! 쾅!' : '거의 다 됐어요!';
    if (say !== lastBubble) { lastBubble = say; bubbleBorn = t; if (say) drawBubble(say); }
    bubble.visible = opts.bubble !== false && !!say && (mode !== 3 || maint > 0.5) && tk > 0.25;
    if (bubble.visible) { const k = easeBack(Math.min(1, (t - bubbleBorn) / 0.3)); bubble.scale.set(0.5 * k, 0.195 * k, 1); { const d = sign.visible ? -0.2 : -0.13, off = new THREE.Vector3(d, 0, 0);
        if (camera) { const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0); right.y = 0; right.normalize().transformDirection(root.matrixWorld.clone().invert()); off.copy(right).multiplyScalar(d); }
        bubble.position.set(px + off.x, y + hy + (sign.visible ? 0.1 : mode === 3 ? 0.2 : 0.14), off.z); } }
    // done: check mark + confetti
    check.visible = ph === 'done';
    if (check.visible) {
      check.scale.setScalar(Math.max(0.0001, easeBack(Math.min(1, phT / 0.35))) * 1.3);
      check.position.set(px, y + robot.scale.y * (hy + 0.145) + 0.15 + Math.sin(t * 4) * 0.008, 0);
      if (camera) { check.quaternion.copy(root.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(camera.quaternion)); check.rotateZ(Math.sin(t * 3) * 0.12); }
      if (!doneBurst) { doneBurst = true; burstConfetti(new THREE.Vector3(px, y + hy + 0.2, 0)); }
    }
    for (const c of confetti) {
      const u = c.userData; if (u.life <= 0) continue;
      u.life -= dt; u.v.y -= 1.6 * dt; u.v.multiplyScalar(1 - dt * 1.2); c.position.addScaledVector(u.v, dt);
      c.rotation.x += u.w.x * dt; c.rotation.y += u.w.y * dt; c.rotation.z += u.w.z * dt;
      c.material.opacity = Math.min(1, u.life * 2); c.visible = u.life > 0;
    }

    // ----- X-ray fault view -----
    xray = ease(xray, mode === 2 ? 1 : 0, 4, dt);
    bodyMat.opacity = 1 - 0.68 * xray;
    inner.visible = cpu.visible = xray > 0.02;
    if (inner.visible) {
      const hot = Math.sin(t * 12) > 0 ? 1 : 0.35;
      motorMat.emissiveIntensity = 1.6 * hot * xray;
      heat.material.opacity = 0.35 * hot * xray; heat.scale.setScalar(1 + Math.sin(t * 12) * 0.08);
      motor.position.x = Math.sin(t * 60) * 0.002;
      innerGears.forEach((g, i) => g.rotation.z += dt * (i ? -1 : 1) * (2 + Math.random() * 6));
    }

    // ----- face icons -----
    let icon = null;
    if (mode === 1 && t % 4 > 2.5) icon = 'warn';
    if (mode === 2 && t % 1.6 > 0.8) icon = 'err';
    if (mode === 3 && ph === 'done') icon = 'check';
    if (tk < 0.25) icon = null;
    iconPlane.visible = !!icon;
    if (icon) { iconMat.map = iconTex[icon]; iconMat.opacity = mode === 2 ? (strobeNow(t) ? 1 : 0.55) : 1; }
    eyes.forEach(e => e.visible = !icon);

    // ----- status glow -----
    const sc = STATUS[mode];
    floorGlowMat.color.lerp(sc, Math.min(1, dt * 6));
    const pulse = mode === 2 ? 0.55 + 0.45 * (strobeNow(t) ? 1 : 0) : 0.75 + 0.25 * Math.sin(t * (mode === 1 ? 5 : 2));
    floorGlowMat.opacity = 0.55 * pulse;
    floorGlow.position.x = px; floorGlow.scale.setScalar(1 - (y - baseY) * 1.5);

    // ----- warning sign above the head -----
    if (sign.visible) {
      sign.position.set(px, y + robot.scale.y * (hy + 0.145) + 0.075 + (mode === 3 ? 0.06 : 0) + Math.sin(t * (mode === 2 ? 10 : 4)) * 0.012, 0);
      sign.scale.setScalar(mode === 2 ? 1 + Math.max(0, Math.sin(t * 14)) * 0.15 : 1);
      signMat.emissiveIntensity = mode === 2 ? (Math.sin(t * 14) > 0 ? 2.2 : 0.6) : 1.3;
    }
    // ----- fault alarm -----
    const danger = mode === 2, strobe = Math.sin(t * 14) > 0 ? 1 : 0;
    glassMat.color.copy(glassBase).lerp(glassRed, danger ? strobe * 0.8 : 0);
    rings.forEach((r, i) => {
      r.visible = danger;
      if (!danger) return;
      const q = (t * 1.1 + i / 3) % 1;
      r.scale.setScalar(0.12 + q * 0.55);
      r.material.opacity = (1 - q) * 0.7;
    });
  };

  const holder = new THREE.Group(); holder.name = 'robot_holder'; holder.add(root); root.position.y = -baseY;
  return { root: holder, setMode, update };
}
