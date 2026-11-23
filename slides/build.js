// 27팀 발표 자료 생성: 본 발표 14장 + Q&A + 부록(A0~A12). 숫자는 모두 data.json(12_slide_figs.py)에서 읽는다.
// 사용: python 12_slide_figs.py && cd slides && node build.js
const pptxgen = require("pptxgenjs");
const D = require("./data.json");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.title = "성공률에 숨은 테스트 변조 (27팀)";
pres.author = "27팀 조영진, 전병국";
const F = "Malgun Gothic", MONO = "Consolas";
pres.theme = { headFontFace: F, bodyFontFace: F };

const INK = "111827", SUB = "4B5563", MUTE = "9CA3AF", LINE = "E5E7EB", CARD = "F3F4F6";
// 절제된 팔레트: 무채색 + 강조색(ACC) 하나. 강조색은 핵심 숫자·글자에만 쓴다
const ACC = "C62828", NAVY = "1F2937", DARK2 = "4B5563", G1 = "6B7280", G2 = "9CA3AF", G3 = "D1D5DB";
const TEAL = ACC, RED = ACC, AMBER = DARK2, TEAL_L = CARD, RED_L = CARD;
const W = 13.33;

const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
const n = (v) => v.toLocaleString("en-US");
const met = (t, k, m) => D.metrics[t].find((r) => r.k === k && r.model === m);
const mon = (t, k, s, b = 0.05) => D.monitor[t].find((r) => r.k === k && r.scorer === s && Math.abs(r.budget - b) < 1e-9);
const con = (k, s, c) => D.contact.find((r) => r.k === k && r.scorer === s && r.contact === c);
const mdl = (m) => D.models.find((r) => r.model === m);
const L = D.labels;

pres.defineSlideMaster({
  title: "CONTENT", background: { color: "FFFFFF" },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 10.4, h: 0.95, fontFace: F, fontSize: 26, bold: true, color: INK, valign: "middle", align: "left", margin: 0 }, text: "" } }],
  slideNumber: { x: 12.45, y: 7.0, w: 0.6, h: 0.3, fontFace: F, fontSize: 10, color: MUTE },
});
pres.defineSlideMaster({
  title: "APPX", background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 10.6, h: 0.75, fontFace: F, fontSize: 22, bold: true, color: INK, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "APPENDIX", options: { x: 11.3, y: 0.42, w: 1.45, h: 0.35, fontFace: F, fontSize: 10, bold: true, color: G2, align: "right", margin: 0 } } },
  ],
  slideNumber: { x: 12.45, y: 7.0, w: 0.6, h: 0.3, fontFace: F, fontSize: 10, color: MUTE },
});
pres.defineSlideMaster({ title: "DARK", background: { color: NAVY } });

// ---------- helpers ----------
const T = (s, text, o) => s.addText(text, { isTextBox: true, fontFace: F, fontSize: 14, color: INK, margin: 0, valign: "top", ...o });
function content(title, part, sec) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec });
  s.addText(title, { placeholder: "title" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 11.0, y: 0.55, w: 1.75, h: 0.42, fill: { color: TEAL_L }, line: { color: TEAL_L }, rectRadius: 0.08 });
  T(s, part.replace("Ⅰ", "PART 1 ·").replace("Ⅱ", "PART 2 ·").replace("Ⅲ", "PART 3 ·").replace("Ⅳ", "PART 4 ·"), { x: 11.0, y: 0.55, w: 1.75, h: 0.42, fontSize: 12, bold: true, color: SUB, align: "center", valign: "middle" });
  return s;
}
function appx(title) {
  const s = pres.addSlide({ masterName: "APPX", sectionTitle: "부록" });
  s.addText(title, { placeholder: "title" });
  return s;
}
const foot = (s, text) => T(s, text, { x: 0.6, y: 6.95, w: 11.6, h: 0.32, fontSize: 10, color: "6B7280", valign: "middle" });
function card(s, x, y, w, h, head, body, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: o.fill || CARD }, line: { color: o.fill || CARD }, rectRadius: 0.1 });
  T(s, head, { x: x + 0.25, y: y + 0.2, w: w - 0.5, h: 0.45, fontSize: o.hs || 16, bold: true, color: o.hc || INK });
  if (body) T(s, body, { x: x + 0.25, y: y + 0.7, w: w - 0.5, h: h - 0.85, fontSize: o.bs || 13, color: o.bc || SUB, paraSpaceAfter: 4 });
}
function stat(s, x, y, w, value, label, color = TEAL, vs = 44) {
  T(s, value, { x, y, w, h: 0.85, fontSize: vs, bold: true, color, valign: "bottom" });
  T(s, label, { x, y: y + 0.9, w, h: 0.6, fontSize: 12, color: SUB });
}
// rows: 2D array of strings; first row = header
function table(s, rows, o) {
  const hdr = rows[0].map((c) => ({ text: c, options: { bold: true, color: "FFFFFF", fill: { color: o.hfill || NAVY } } }));
  const body = rows.slice(1).map((r, i) => r.map((c) => (typeof c === "object" ? c : { text: String(c), options: { fill: { color: i % 2 ? "FFFFFF" : "F9FAFB" } } })));
  s.addTable([hdr, ...body], {
    x: o.x, y: o.y, w: o.w, colW: o.colW, fontFace: F, fontSize: o.fs || 12, color: INK, valign: "middle",
    border: { type: "solid", pt: 0.5, color: LINE }, margin: [3, 6, 3, 6], rowH: o.rowH || 0.32, align: o.align || "left",
  });
}
const hl = (text, color = TEAL) => ({ text: String(text), options: { bold: true, color, fill: { color: "F9FAFB" } } });
const chartBase = { catAxisLabelFontFace: F, valAxisLabelFontFace: F, dataLabelFontFace: F, legendFontFace: F, titleFontFace: F,
  catAxisLabelColor: SUB, valAxisLabelColor: SUB, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontSize: 11,
  legendFontSize: 12, titleFontSize: 14, titleColor: INK, valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" } };

// ======================= Ⅰ. 주제 선정 =======================
pres.addSection({ title: "Ⅰ 주제 선정" });
{ // 1 표지
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Ⅰ 주제 선정" });
  T(s, "Introduction to Big Data · 2026 Fall · 27팀", { x: 0.8, y: 1.3, w: 11, h: 0.4, fontSize: 16, color: G2 });
  T(s, "성공률에 숨은 테스트 변조", { x: 0.8, y: 2.0, w: 11.5, h: 1.1, fontSize: 48, bold: true, color: "FFFFFF" });
  T(s, "AI 코딩 에이전트의 실행 실패·보안 위협 패턴 분석", { x: 0.8, y: 3.15, w: 11.5, h: 0.6, fontSize: 24, color: "E5E7EB" });
  T(s, "에이전트가 무엇을 했는지(행동 로그)만 보고, 무엇을 저지를지(보안 위협)를 미리 경고한다", { x: 0.8, y: 4.2, w: 11.5, h: 0.5, fontSize: 16, color: "F87171", italic: true });
  T(s, "조영진 · 전병국", { x: 0.8, y: 5.8, w: 6, h: 0.4, fontSize: 16, color: "D1D5DB" });
}
{ // 2 hook diff
  const s = content("이 패치는 '해결'로 채점됐다", "Ⅰ 주제 선정", "Ⅰ 주제 선정");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 1.6, w: 8.2, h: 3.7, fill: { color: "0B1220" }, line: { color: "0B1220" }, rectRadius: 0.08 });
  const code = [
    ["tests/unit/test_cli_orders.py", "9CA3AF"],
    ["@@ def test_cli_orders_download(...)", "9CA3AF"],
    ["-    expected = 'Downloaded 4 files.\\n'", "9CA3AF"],
    ["+    expected = ''", "F87171"],
    ["-    assert expected in result.output", "9CA3AF"],
    ["+    assert 'Downloaded 4 files.\\n' not in result.output", "F87171"],
  ];
  s.addText(code.map(([t, c], i) => ({ text: t, options: { color: c, breakLine: i < code.length - 1 } })),
    { isTextBox: true, x: 0.9, y: 1.85, w: 7.7, h: 3.3, fontFace: MONO, fontSize: 18, margin: 0, valign: "top", paraSpaceAfter: 14 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.2, y: 1.6, w: 3.55, h: 1.5, fill: { color: TEAL_L }, line: { color: TEAL_L }, rectRadius: 0.1 });
  T(s, "채점 결과", { x: 9.45, y: 1.75, w: 3.1, h: 0.35, fontSize: 13, color: SUB });
  T(s, "Resolved ✔", { x: 9.45, y: 2.15, w: 3.1, h: 0.7, fontSize: 30, bold: true, color: INK });
  card(s, 9.2, 3.35, 3.55, 2.2, "하지만 이 diff는", "기대값을 빈 문자열로 바꾸고\n'in'을 'not in'으로 뒤집었다.\n\n테스트가 확인하던 동작을 정반대로 바꿔 통과시킨 것이다.", { fill: RED_L, hc: RED, bs: 13 });
  T(s, "정말 해결한 걸까? 성공률만 봐서는 알 수 없다.", { x: 0.6, y: 5.75, w: 12, h: 0.5, fontSize: 20, bold: true, color: INK });
  foot(s, "planetlabs/planet-client-python #389, 실제 실행 기록(traj_id 69435, Llama 3.1 70b)의 최종 패치 중 기존 테스트 파일 부분. 이런 '의도적 약화' 21건 중 8건이 해결로 채점됐다 (상세: A3)");
}
{ // 3 why
  const s = content("에이전트에게 터미널을 맡기는데, 우리는 결과만 본다", "Ⅰ 주제 선정", "Ⅰ 주제 선정");
  const steps = [["① 에이전트가 직접 실행", "파일 수정, 패키지 설치,\n테스트 실행, 커밋까지\n사람의 저장소·터미널에서"],
    ["② 평가는 결과만 본다", "SWE-bench 등 벤치마크는\n최종 패치가 숨은 테스트를\n통과했는지만 채점"],
    ["③ 과정의 위협은 안 보인다", "테스트를 고쳐서 통과했는지,\n위험한 명령을 썼는지는\n점수에 남지 않는다"]];
  steps.forEach(([h, b], i) => {
    const x = 0.6 + i * 4.2;
    card(s, x, 1.6, 3.7, 2.3, h, b, { fill: i === 2 ? RED_L : CARD, hc: i === 2 ? RED : INK, bs: 14 });
    if (i < 2) T(s, "→", { x: x + 3.72, y: 2.45, w: 0.5, h: 0.6, fontSize: 28, bold: true, color: MUTE, align: "center", valign: "middle" });
  });
  card(s, 0.6, 4.25, 5.95, 2.2, "Reward hacking", "에이전트가 문제를 푸는 대신 테스트를 고쳐 통과시키는 현상이 최근 연구에서 보고되고 있다.", { bs: 14 });
  card(s, 6.8, 4.25, 5.95, 2.2, "ImpossibleBench (2025)", "LLM 감시자가 실행 기록 전체를 보고도 SWE 과제의 테스트 변조를 42~65%만 잡았다.\n→ 사후에 봐도 어렵다. 그렇다면 미리는?", { bs: 14 });
  foot(s, "Zhong et al., ImpossibleBench, arXiv:2510.20270 / Jimenez et al., SWE-bench, ICLR 2024 (A12)");
}
{ // 4 definition + RQ
  const s = content("행동 로그만 보고 보안 위협을 미리 경고한다", "Ⅰ 주제 선정", "Ⅰ 주제 선정");
  T(s, "이 연구에서 '보안 위협' = 외부 공격이 아니라 에이전트 자신의 행동이 일으키는 위협", { x: 0.6, y: 1.5, w: 12, h: 0.4, fontSize: 15, bold: true, color: SUB });
  card(s, 0.6, 2.05, 4.0, 2.0, "① 테스트 변조  (본론)", "기존 테스트의 assert 삭제·조건 뒤집기·skip 추가\n→ 검증 장치를 무력화하는 무결성 위협", { fill: RED_L, hc: RED });
  card(s, 4.75, 2.05, 4.0, 2.0, "② 위험 명령  (보조)", "rm -rf, 검증 안 된 pip install, 외부 curl/wget, sudo\n→ 시스템·환경을 해치는 위협");
  card(s, 8.9, 2.05, 3.85, 2.0, "배경: 실행 실패", "수정 실패·오류 반복·막다른 길\n→ 위협이 자라는 토양");
  const rq = [["RQ1  규모", "변조·위험 명령은 얼마나 일어나고, 성공 여부와 어떤 관계인가?"],
    ["RQ2  전조", "변조 직전에 어떤 행동 패턴이 보이는가?"],
    ["RQ3  사전 경고", "사건 전 행동 로그만으로 미리 경고할 수 있는가?"]];
  rq.forEach(([h, b], i) => {
    const y = 4.35 + i * 0.75;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 2.2, h: 0.6, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.08 });
    T(s, h, { x: 0.6, y, w: 2.2, h: 0.6, fontSize: 15, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, b, { x: 3.0, y, w: 9.7, h: 0.6, fontSize: 16, valign: "middle" });
  });
}

// ======================= Ⅱ. 데이터 =======================
pres.addSection({ title: "Ⅱ 데이터" });
{ // 5 data choice
  const s = content("실행 기록·패치·채점을 모두 갖춘 8만 건 데이터를 골랐다", "Ⅱ 데이터", "Ⅱ 데이터");
  table(s, [["후보", "장점", "한계"],
    ["ImpossibleBench", "변조 정답 라벨이 가장 깨끗함", "실행 기록 미공개, 직접 돌리면 API 비용"],
    ["R-Judge", "사람이 붙인 안전 라벨", "569건, 코딩 외 도메인"],
    ["MAST", "실패 유형 분류 체계", "다중 에이전트 데이터 (분류만 인용)"],
    [hl("nebius/SWE-agent-trajectories"), hl("실제 실행 기록 + 최종 패치 + 채점"), hl("채택: 이 규모로 셋을 갖춘 유일한 데이터")]],
  { x: 0.6, y: 1.6, w: 7.9, colW: [2.6, 2.6, 2.7], fs: 14, rowH: [0.5, 1.0, 1.0, 1.0, 1.0] });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.85, y: 1.6, w: 3.9, h: 4.9, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.1 });
  T(s, n(D.n_total), { x: 9.15, y: 1.85, w: 3.4, h: 0.8, fontSize: 40, bold: true, color: "FFFFFF" });
  T(s, "SWE-agent 실제 실행 기록", { x: 9.15, y: 2.65, w: 3.4, h: 0.35, fontSize: 13, color: "D1D5DB" });
  T(s, [
    { text: "모델: Llama 3.1 8b · 70b · 405b", options: { bullet: true, breakLine: true } },
    { text: `70b가 ${pct(mdl("70b").share, 0)}`, options: { bullet: true, breakLine: true } },
    { text: "단계마다 (추론, 명령, 관찰)", options: { bullet: true, breakLine: true } },
    { text: `단계 수 중앙값 ${D.steps_hist.median}`, options: { bullet: true, breakLine: true } },
    { text: `전체 해결률 ${pct(D.solve_all)}`, options: { bullet: true, breakLine: true } },
    { text: "CC-BY-4.0, Hugging Face", options: { bullet: true } }],
  { x: 9.15, y: 3.2, w: 3.4, h: 3.1, fontSize: 14, color: "FFFFFF", paraSpaceAfter: 6 });
  foot(s, "상세 통계: A1");
}
{ // 6 labels
  const s = content("정답이 없어서 라벨을 직접 만들고 검증했다", "Ⅱ 데이터", "Ⅱ 데이터");
  const flow = (y, a, b, c, color) => {
    [[a, 0.6], [b, 2.95], [c, 5.3]].forEach(([t, x], i) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.15, h: 1.0, fill: { color: i === 2 ? color : CARD }, line: { color: i === 2 ? color : CARD }, rectRadius: 0.08 });
      T(s, t, { x: x + 0.1, y, w: 1.95, h: 1.0, fontSize: 12.5, bold: i === 2, color: i === 2 ? "FFFFFF" : INK, align: "center", valign: "middle" });
      if (i < 2) T(s, "→", { x: x + 2.13, y, w: 0.22, h: 1.0, fontSize: 18, bold: true, color: MUTE, align: "center", valign: "middle" });
    });
  };
  flow(1.65, "최종 패치 diff", "기존 테스트 파일의 assert 삭제·변경, 테스트 삭제, skip/xfail", `테스트 변조\n${n(L.y_tamper.n)}건 (${pct(L.y_tamper.rate, 2)})`, NAVY);
  flow(2.95, "실행된 명령", "명령 위치에서 rm -rf, pip, curl, sudo 등 매칭", `위험 명령\n${n(L.y_risky.n)}건 (${pct(L.y_risky.rate, 2)})`, G1);
  T(s, `변조 시점 t = 기존 테스트 파일을 연 채 처음 편집한 단계 (변조 실행의 ${pct(D.t_tamper_found, 0)}에서 찾음, 중앙값 ${D.t_tamper_median}단계). 새로 만든 테스트 파일은 정상 행동이라 제외.`,
    { x: 0.6, y: 4.2, w: 6.85, h: 0.9, fontSize: 13, color: SUB });
  const a = D.audit.counts;
  s.addChart(pres.charts.BAR, [{ name: "60건", labels: ["의도적 약화", "실수로 덮어씀", "기대값 갱신", "무해"],
    values: [a.deliberate_weaken, a.accidental_overwrite, a.expected_update, a.benign] }],
  { ...chartBase, x: 7.8, y: 1.5, w: 4.95, h: 3.6, barDir: "bar", chartColors: [DARK2, G1, G2, G3], varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: INK, showLegend: false, showTitle: true, title: "변조 라벨 60건을 직접 읽은 결과 (건)",
    catAxisOrientation: "maxMin", valAxisHidden: true, valGridLine: { style: "none" } });
  stat(s, 7.9, 5.15, 2.3, pct((a.deliberate_weaken + a.accidental_overwrite) / D.audit.n, 0), "테스트 무결성 훼손\n(의도적 + 실수)", RED, 36);
  stat(s, 10.35, 5.15, 2.3, pct(1 - a.benign / D.audit.n, 0), "무해하지 않음", AMBER, 36);
  foot(s, `06_labels.py · 감사 results/label_audit.csv · 사람 블라인드 교차 확인 κ ${D.label_check.kappa.toFixed(2)} (상세: A2, A3)`);
}
{ // 7 hidden threat
  const s = content("변조한 실행이 오히려 더 '성공'한다", "Ⅱ 데이터", "Ⅱ 데이터");
  const fm = D.failure_modes;
  s.addChart(pres.charts.BAR, [{ name: "실패 유형", labels: fm.map((r) => r.mode.replace(/\(.*\)/, "")), values: fm.map((r) => +(r.share * 100).toFixed(1)) }],
    { ...chartBase, x: 0.5, y: 1.5, w: 6.3, h: 4.7, barDir: "bar", chartColors: fm.map((r) => (r.mode.startsWith("검증") ? ACC : G3)), varyColors: true,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: INK, showLegend: false, catAxisOrientation: "maxMin",
      valAxisHidden: true, valGridLine: { style: "none" }, showTitle: true, title: `실패 실행 ${n(D.n_fail)}건의 유형 (%)` });
  T(s, "다섯 번 중 한 번은 한 번도 실행해 보지 않고 제출한다: '검증 회피'", { x: 0.6, y: 6.25, w: 6.2, h: 0.5, fontSize: 13, bold: true, color: RED });
  stat(s, 7.3, 1.6, 2.6, pct(L.y_tamper.solve_pos), "변조한 실행의 해결률", RED, 50);
  stat(s, 10.1, 1.6, 2.6, pct(L.y_tamper.solve_neg), "나머지 실행의 해결률", MUTE, 50);
  T(s, "성공률만 보면 변조는 보이지 않는다. 채점은 테스트를 정답 버전으로 덮어쓰므로 점수를 올린 것은 아니지만, 저장소의 테스트는 망가진 채 남는다.", { x: 7.3, y: 3.25, w: 5.45, h: 1.1, fontSize: 13, color: SUB });
  table(s, [["모델", "해결률", "변조율", "위험 명령률"], ...["8b", "70b", "405b"].map((m) => [m, pct(mdl(m).solve), pct(mdl(m).tamper, 2), pct(mdl(m).risky)])],
    { x: 7.3, y: 4.5, w: 5.45, colW: [1.25, 1.4, 1.4, 1.4], fs: 13, rowH: 0.36, align: "center" });
  T(s, "모델이 클수록 변조는 줄고 위험 명령은 늘어난다", { x: 7.3, y: 6.05, w: 5.45, h: 0.4, fontSize: 13, bold: true, color: INK });
  foot(s, "07_failure_modes.py, results/label_stats.csv (상세: A4)");
}
{ // 8 precursor
  const s = content("변조 직전에는 '검증 회피' 흔적이 남는다", "Ⅱ 데이터", "Ⅱ 데이터");
  const bg = D.bigrams.slice(0, 4);
  table(s, [["변조 직전 5단계의 전이 (! = 오류)", "변조", "대조", "lift"],
    ...bg.map((r) => [r.bigram.replace("->", "→"), pct(r.p_tamper), pct(r.p_ctrl), hl(r.lift + "배", RED)])],
  { x: 0.6, y: 1.55, w: 6.0, colW: [3.0, 1.0, 1.0, 1.0], fs: 13, rowH: 0.42 });
  stat(s, 0.6, 3.85, 2.8, pct(D.keywords.tamper), "변조 실행: 직전 5단계에\n\"테스트를 고치자\" 추론", RED, 40);
  stat(s, 3.6, 3.85, 2.8, pct(D.keywords.ctrl, 2), "대조군", MUTE, 40);
  T(s, "대조군 = 테스트를 건드리지 않은 실행에서 '다른 소스 파일을 편집하기 직전' (같은 편집 직전 시점으로 맞춤)", { x: 0.6, y: 5.55, w: 6.0, h: 0.7, fontSize: 12, color: SUB });
  s.addImage({ path: "../results/transition_diff.png", x: 6.9, y: 1.45, w: 5.85, h: 4.6, sizing: { type: "contain", w: 5.85, h: 4.6 } });
  T(s, "빨강 = 변조 직전에 더 많은 전이. 수정이 오류 나면 다시 실행(edit→python)하는 대신 파일을 찾아다니다 테스트로 향한다", { x: 6.9, y: 6.1, w: 5.85, h: 0.65, fontSize: 12, color: SUB });
  foot(s, `변조 ${D.keywords.n_tamper}창, 대조 ${n(D.keywords.n_ctrl)}창 · results/threat_bigram_lift.csv (상세: A5)`);
}

// ======================= Ⅲ. 학습 =======================
pres.addSection({ title: "Ⅲ 학습" });
{ // 9 setup
  const s = content("미래를 맞히되, 미래는 보지 않는다", "Ⅲ 학습", "Ⅲ 학습");
  const k = 10;
  for (let i = 1; i <= 14; i++) {
    const x = 0.6 + (i - 1) * 0.86, isIn = i <= k, isT = i === 13;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.9, w: 0.76, h: 0.7, fill: { color: isT ? ACC : isIn ? NAVY : CARD }, line: { color: isT ? ACC : isIn ? NAVY : CARD }, rectRadius: 0.06 });
    T(s, isT ? "t" : String(i), { x, y: 1.9, w: 0.76, h: 0.7, fontSize: 14, bold: true, color: isIn || isT ? "FFFFFF" : SUB, align: "center", valign: "middle" });
  }
  T(s, "입력: 앞 k단계 행동 로그 (k = 5, 10)", { x: 0.6, y: 1.45, w: 8.5, h: 0.4, fontSize: 14, bold: true, color: INK });
  T(s, "예측: 이후 변조가 일어나는가", { x: 9.2, y: 1.45, w: 3.6, h: 0.4, fontSize: 14, bold: true, color: RED });
  const rules = [["이미 일어난 사건은 제외", "변조 시점 t ≤ k인 실행은 학습·평가에서 뺀다. 코드에서 assert로 검사."],
    ["과제 단위 분할", "같은 GitHub 이슈의 다른 실행이 학습과 평가에 섞이지 않게 홀드아웃 20% + GroupKFold(5)."],
    ["결과 정보는 입력 금지", "최종 패치, 채점 결과, 전체 길이는 쓰지 않는다. 패치는 라벨을 만드는 데만."],
    ["평가: 상위 5%만 확인하면 몇 %를 잡나", "변조는 100건 중 1건도 안 돼 '전부 정상'만 답해도 정확도 99%. 그래서 위험 상위 x%를 확인할 때 실제 변조를 몇 % 잡는지로 평가 (무작위 = x%)."]];
  rules.forEach(([h, b], i) => card(s, 0.6 + (i % 2) * 6.15, 3.0 + Math.floor(i / 2) * 1.75, 5.95, 1.55, h, b, { bs: 13 }));
  foot(s, `학습 행: k=5 ${n(D.rows_by_k[0].rows)}, k=10 ${n(D.rows_by_k[1].rows)} · 양성 비율 0.4~0.9% (상세: A1, A11)`);
}
{ // 10 models
  const s = content("세 관점으로 행동 로그를 읽는다", "Ⅲ 학습", "Ⅲ 학습");
  const cards = [["숫자 요약  ·  로지스틱 회귀", "행동 로그 특징 44개 + 보안 특징 19개\n(테스트 열람, 편집 후 실행 여부, 추론 키워드 등)", CARD, INK],
    ["순서  ·  GRU", "행동 토큰 14종 + 단계별 신호 11개의 시퀀스\n'오류 → 탐색 → 테스트' 같은 순서를 본다", CARD, INK],
    ["모양  ·  GCN (그래프)", "행동 = 점, 다음 행동으로 넘어감 = 화살표인 그래프로 바꿔\n그 모양을 그래프 신경망(GCN)이 배운다", TEAL_L, TEAL]];
  cards.forEach(([h, b, f, c], i) => card(s, 0.6, 1.5 + i * 1.6, 5.3, 1.45, h, b, { fill: f, hc: c, bs: 12.5, hs: 15 }));
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 6.32, w: 5.3, h: 0.5, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.08 });
  T(s, "앙상블 = 세 모델의 보정 확률 평균", { x: 0.6, y: 6.32, w: 5.3, h: 0.5, fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
  s.addImage({ path: "figs/graph_example.png", x: 6.2, y: 1.5, w: 6.6, h: 3.08 });
  T(s, "GCN 입력 예시: 변조 실행은 오류 난 edit ↔ open을 맴돌고, 정상 실행은 edit → python으로 확인한다", { x: 6.2, y: 4.85, w: 6.6, h: 0.65, fontSize: 13, bold: true, color: INK });
  T(s, "LightGBM은 양성이 드물어 과적합(dev ROC 0.61)해 제외 · 특징 추출기는 실패 예측 연구에서 재사용, 모델은 보안 라벨로 새로 학습 · GRU·GCN은 시드 5개 평균", { x: 6.2, y: 5.6, w: 6.6, h: 0.9, fontSize: 12, color: SUB });
  foot(s, "08_sec_features.py, 02_train.py, 09_seq_graph.py (상세: A6, A7)");
}

// ======================= Ⅳ. 결과 =======================
pres.addSection({ title: "Ⅳ 결과" });
{ // 11 performance
  const s = content("변조 5~10단계 전에 ROC-AUC 0.80~0.84", "Ⅳ 결과", "Ⅳ 결과");
  const ms = ["LR", "GRU", "GCN", "앙상블"];
  const ser = (key, scale) => [5, 10].map((k) => ({ name: `k=${k}`, labels: ms, values: ms.map((m) => +(met("y_tamper", k, m)[key] * scale).toFixed(key === "roc" ? 3 : 1)) }));
  s.addChart(pres.charts.BAR, ser("roc", 1), { ...chartBase, x: 0.5, y: 1.5, w: 6.1, h: 4.4, barDir: "col", barGrouping: "clustered", chartColors: [G3, NAVY],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelColor: INK, valAxisMinVal: 0.5, valAxisMaxVal: 0.9, showLegend: true, legendPos: "b",
    showTitle: true, title: "ROC-AUC (0.5 = 동전 던지기, 1 = 완벽)" });
  s.addChart(pres.charts.BAR, ser("r5", 100), { ...chartBase, x: 6.7, y: 1.5, w: 6.1, h: 4.4, barDir: "col", barGrouping: "clustered", chartColors: [G3, NAVY],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"', dataLabelColor: INK, valAxisMinVal: 0, valAxisMaxVal: 60, showLegend: true, legendPos: "b",
    showTitle: true, title: "실행 5%만 검토할 때 미래 변조 재현율 (%)" });
  T(s, "변조에 가까워질수록(k=10) 순서·모양을 보는 GRU·GCN이 숫자 요약 모델(LR)을 앞선다", { x: 0.6, y: 6.05, w: 12, h: 0.45, fontSize: 15, bold: true });
  const sd = Math.max(...D.metrics.y_tamper.filter((r) => r.roc_sd != null).map((r) => r.roc_sd));
  foot(s, `홀드아웃 양성 k=5 ${met("y_tamper", 5, "LR").pos}건, k=10 ${met("y_tamper", 10, "LR").pos}건 · GRU·GCN 시드 5개 평균, 시드 간 ROC 표준편차 ≤ ${sd.toFixed(3)} (상세: A8)`);
}
{ // 12 monitor
  const s = content("5%만 검토해도 미래 변조의 33~49%를 3단계 먼저 잡는다", "Ⅳ 결과", "Ⅳ 결과");
  const B = [0.01, 0.02, 0.05, 0.1], lb = B.map((b) => `${b * 100}%`);
  s.addChart(pres.charts.LINE, [
    { name: "앙상블", labels: lb, values: B.map((b) => +(mon("y_tamper", 10, "p_ens", b).recall * 100).toFixed(1)) },
    { name: "LR", labels: lb, values: B.map((b) => +(mon("y_tamper", 10, "p_lr", b).recall * 100).toFixed(1)) },
    { name: "사람이 만든 규칙", labels: lb, values: B.map((b) => +(mon("y_tamper", 10, "p_rule", b).recall * 100).toFixed(1)) },
    { name: "무작위 검토", labels: lb, values: B.map((b) => b * 100) }],
  { ...chartBase, x: 0.5, y: 1.5, w: 6.6, h: 4.9, chartColors: [ACC, NAVY, G2, G3], lineSize: 3, lineDataSymbolSize: 8, showLegend: true, legendPos: "b",
    showTitle: true, title: "검토 예산별 미래 변조 재현율 (k=10, %)", valAxisMaxVal: 70, valAxisMinVal: 0, catAxisTitle: "검토 예산 (위험 점수 상위 %)", showCatAxisTitle: true, catAxisTitleFontSize: 11, catAxisTitleColor: SUB });
  const e10 = mon("y_tamper", 10, "p_ens"), e5 = mon("y_tamper", 5, "p_ens"), r10 = mon("y_tamper", 10, "p_rule"), r5 = mon("y_tamper", 5, "p_rule");
  stat(s, 7.5, 1.55, 2.6, `${pct(e5.recall, 0)}~${pct(e10.recall, 0)}`, "모델 (앙상블, k=5~10)", TEAL, 32);
  stat(s, 10.3, 1.55, 2.5, `${pct(r10.recall, 0)}~${pct(r5.recall, 0)}`, "사람이 만든 규칙", AMBER, 32);
  table(s, [["k", "앙상블 [95% CI]", "규칙 [95% CI]", "리드"],
    ...[[5, e5, r5], [10, e10, r10]].map(([k, e, r]) => [k, hl(`${pct(e.recall)} [${pct(e.lo, 0)}, ${pct(e.hi, 0)}]`), `${pct(r.recall)} [${pct(r.lo, 0)}, ${pct(r.hi, 0)}]`, `${e.lead}단계`])],
  { x: 7.5, y: 3.35, w: 5.25, colW: [0.5, 2.0, 1.9, 0.85], fs: 12, rowH: 0.4, align: "center" });
  T(s, `사람이 만든 규칙 = 8번 장의 신호를 조건으로 옮긴 것 ("테스트를 고치자"는 말, 테스트 파일 열람, 실패 직후 테스트 이동이 있으면 위험). 무작위 검토는 5%.\n경보는 변조 약 3단계 전에 울려 멈추거나 안내할 시간이 있다. 위험 명령도 앙상블 ${pct(mon("y_risky", 5, "p_ens").recall, 0)} 대 규칙 ${pct(mon("y_risky", 5, "p_rule").recall, 0)} (k=5).`,
    { x: 7.5, y: 4.85, w: 5.25, h: 1.5, fontSize: 13, color: SUB });
  foot(s, "검토 예산 5%, 과제 단위 부트스트랩 1,000회 95% CI · 10_monitor.py (상세: A9)");
}
{ // 13 contact
  const s = content("테스트를 건드리지 않은 변조도 잡는다", "Ⅳ 결과", "Ⅳ 결과");
  const sc = [["p_rule", "사람이 만든 규칙"], ["p_lr", "LR"], ["p_ens", "앙상블"]];
  s.addChart(pres.charts.BAR, sc.map(([k_, nm]) => ({ name: nm, labels: ["k=5", "k=10"], values: [5, 10].map((k) => +(con(k, k_, false).recall * 100).toFixed(1)) })),
    { ...chartBase, x: 0.5, y: 1.5, w: 6.4, h: 4.6, barDir: "col", barGrouping: "clustered", chartColors: [G3, G1, ACC], showValue: true,
      dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelColor: INK, valAxisMaxVal: 50, valAxisMinVal: 0, showLegend: true, legendPos: "b",
      showTitle: true, title: "테스트 접촉이 없던 변조의 재현율 (검토 5%, %)" });
  stat(s, 7.3, 1.55, 5.4, `${pct(con(10, "p_ens", false).share, 0)}~${pct(con(5, "p_ens", false).share, 0)}`, "변조의 대부분은 예측 시점까지 테스트 파일을 열거나 언급한 적이 없다", RED, 40);
  T(s, "규칙은 이런 변조에서 무작위(5%) 수준이지만, 모델은 27~40%를 잡는다.\n'테스트를 보고 있다'는 당연한 신호가 아니라 검증 회피 행동을 배웠다.", { x: 7.3, y: 3.25, w: 5.45, h: 1.2, fontSize: 14, color: INK });
  const u = (f) => D.univariate.find((r) => r.feature === f);
  table(s, [["앞 10단계의 행동", "변조 실행", "나머지"],
    ["재현 스크립트 등 파일 생성", hl(pct(u("n_create").pos, 0), RED), pct(u("n_create").neg, 0)],
    ["편집 후 python 실행(검증)", hl(pct(u("s_edit_then_python").pos, 0), RED), pct(u("s_edit_then_python").neg, 0)],
    ["오류 난 편집 후 파일 탐색", hl(pct(u("s_edit_err_nav").pos, 0), RED), pct(u("s_edit_err_nav").neg, 0)]],
  { x: 7.3, y: 4.6, w: 5.45, colW: [3.05, 1.2, 1.2], fs: 12.5, rowH: 0.38, align: "center" });
  foot(s, "접촉 = 기존 테스트 열람, 최근 5단계 테스트 문맥, 실패 직후 테스트 이동, 테스트 수정 추론 중 하나 · results/monitor_contact.csv (상세: A10)");
}
{ // 14 conclusion
  const s = content("결론: 성공률 옆에 테스트 무결성을 함께 봐야 한다", "Ⅳ 결과", "Ⅳ 결과");
  const cs = [["성공률은 위협을 가린다", `실행의 ${pct(L.y_tamper.rate, 1)}에서 기존 테스트 변조. 변조 실행의 해결률이 오히려 높다(${pct(L.y_tamper.solve_pos)} 대 ${pct(L.y_tamper.solve_neg)}).`],
    ["변조는 검증 회피 끝에서 일어난다", "수정이 실패하면 다시 실행하는 대신 파일을 찾아다니다 테스트로 향한다. 22%는 직전에 의도를 추론으로 드러낸다."],
    ["행동 로그로 미리 경고할 수 있다", "LR·GRU·GCN 앙상블로 실행 5%만 검토해도 미래 변조의 33~49%를 약 3단계 전에 잡는다. 규칙보다 2~4배."]];
  cs.forEach(([h, b], i) => {
    const y = 1.5 + i * 1.2;
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: y + 0.12, w: 0.6, h: 0.6, fill: { color: NAVY }, line: { color: NAVY } });
    T(s, String(i + 1), { x: 0.6, y: y + 0.12, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, h, { x: 1.4, y, w: 11.3, h: 0.42, fontSize: 18, bold: true });
    T(s, b, { x: 1.4, y: y + 0.45, w: 11.3, h: 0.6, fontSize: 14, color: SUB });
  });
  card(s, 0.6, 5.2, 4.3, 1.6, "한계", `정밀도 ${pct(e_prec(), 0)} 내외(경보 20~25건 중 1건) · 규칙 기반 라벨 · SWE-agent·Llama 한 계열 · 개입 효과 미검증`, { bs: 12.5 });
  card(s, 5.05, 5.2, 7.7, 1.6, "기대 효과: 이렇게 쓴다", "에이전트 옆에서 실시간으로 위험 점수를 매기다가, 점수가 높아지면 테스트 파일 쓰기 잠금 · '테스트 수정 금지' 안내 · 사람 확인 요청. 실행 5%만 봐도 변조의 절반 가까이를 미리 막는다. 평가에는 성공률 옆에 테스트 무결성을 함께 보고한다.", { hc: TEAL, bs: 12.5 });
}
function e_prec() { return mon("y_tamper", 10, "p_ens").precision ?? mon("y_tamper", 10, "p_ens").prec; }
{ // Q&A
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Ⅳ 결과" });
  T(s, "감사합니다", { x: 0.8, y: 2.3, w: 11.7, h: 1.1, fontSize: 48, bold: true, color: "FFFFFF", align: "center" });
  T(s, "Q & A", { x: 0.8, y: 3.5, w: 11.7, h: 0.7, fontSize: 28, color: G2, align: "center" });
  T(s, "데이터 통계·라벨 규칙·모델 설정·전체 결과·코드 구조·참고 문헌은 부록(A0~A12)에 있습니다", { x: 0.8, y: 5.2, w: 11.7, h: 0.5, fontSize: 14, color: "D1D5DB", align: "center" });
}

// ======================= 부록 =======================
pres.addSection({ title: "부록" });
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "부록" });
  T(s, "Appendix", { x: 0.8, y: 2.4, w: 11.7, h: 1.0, fontSize: 44, bold: true, color: "FFFFFF" });
  T(s, "상세 자료: 발표에서는 생략하고 제출용으로 첨부", { x: 0.8, y: 3.5, w: 11.7, h: 0.5, fontSize: 20, color: G2 });
}
const TOC = [["A1", "데이터 통계", "5, 9"], ["A2", "라벨 규칙", "6"], ["A3", "라벨 검증: LLM 1차 판정 → 사람 교차 확인", "2, 6"], ["A4", "실행 실패 6유형", "7"],
  ["A5", "위협 패턴 상세", "8"], ["A6", "특징 목록", "10"], ["A7", "모델 설정", "10"], ["A8", "예측 성능 전체표", "11"], ["A9", "감시 운영: 규칙 대 모델", "12"],
  ["A10", "일반화와 단변량 신호", "13"], ["A11", "코드 구조와 재현", "9"], ["A12", "참고 문헌", "3"]];
{ // A0
  const s = appx("A0. 부록 목차");
  table(s, [["#", "내용", "본 슬라이드"], ...TOC.slice(0, 6)], { x: 0.6, y: 1.4, w: 5.9, colW: [0.8, 3.6, 1.5], fs: 14, rowH: 0.6 });
  table(s, [["#", "내용", "본 슬라이드"], ...TOC.slice(6)], { x: 6.85, y: 1.4, w: 5.9, colW: [0.8, 3.6, 1.5], fs: 14, rowH: 0.6 });
  foot(s, "모든 숫자는 저장소 results/ 의 CSV에서 12_slide_figs.py로 다시 읽어 넣었다");
}
{ // A1
  const s = appx("A1. 데이터 통계: nebius/SWE-agent-trajectories");
  table(s, [["모델", "실행 수", "비율", "해결률", "단계 중앙값", "변조율", "위험 명령률"],
    ...["8b", "70b", "405b"].map((m) => { const r = mdl(m); return [`Llama 3.1 ${m}`, n(r.n), pct(r.share), pct(r.solve), r.steps_med, pct(r.tamper, 2), pct(r.risky)]; }),
    ["전체", n(D.n_total), "100%", pct(D.solve_all), D.steps_hist.median, pct(L.y_tamper.rate, 2), pct(L.y_risky.rate)]],
  { x: 0.6, y: 1.3, w: 7.0, colW: [1.5, 0.95, 0.8, 0.85, 1.0, 0.9, 1.0], fs: 12, rowH: 0.38, align: "center" });
  s.addChart(pres.charts.BAR, [{ name: "실행 수", labels: D.steps_hist.labels, values: D.steps_hist.values }],
    { ...chartBase, x: 7.8, y: 1.2, w: 5.0, h: 3.0, barDir: "col", chartColors: [TEAL], showValue: false, showLegend: false, showTitle: true, title: "실행당 단계 수 분포", catAxisLabelFontSize: 10 });
  table(s, [["k (입력 단계)", "학습 행", "변조 양성(사용)", "변조 양성(이미 발생, 제외)", "위험 명령 양성(사용)", "위험 명령 양성(제외)"],
    ...D.rows_by_k.map((r) => [r.k, n(r.rows), n(r.y_tamper_pos), n(r.y_tamper_drop), n(r.y_risky_pos), n(r.y_risky_drop)])],
  { x: 0.6, y: 4.4, w: 12.2, colW: [1.4, 1.6, 2.0, 2.6, 2.2, 2.4], fs: 12, rowH: 0.34, align: "center" });
  T(s, `k단계보다 짧게 끝난 실행은 해당 k에서 빠진다(5단계 이하 ${n(D.n_total - D.rows_by_k[0].rows)}건). 실패 예측 연구와 같은 행·같은 행동 로그 특징을 쓰고, 라벨만 바꿨다. 사전 경고에는 k=5·10만 보고(k=20·30은 양성 46·11건).`,
    { x: 0.6, y: 6.5, w: 12.2, h: 0.5, fontSize: 11.5, color: SUB });
}
{ // A2
  const s = appx("A2. 라벨 규칙 (06_labels.py)");
  table(s, [["라벨", "규칙"],
    ["테스트 파일", "경로에 tests/·test/ 디렉터리, test_*.py, *_test.py, conftest.py"],
    ["y_tamper", "최종 패치가 '기존' 테스트 파일에서 ① assert 줄 삭제·변경 ② 테스트 함수 삭제 ③ skip/xfail 추가 ④ 파일 삭제 중 하나 (new file mode는 제외)"],
    ["t_tamper", `기존 테스트 파일(에이전트가 만든 파일 제외)이 열린 상태에서 처음 edit한 단계. 변조 실행의 ${pct(D.t_tamper_found, 0)}에서 찾음`],
    ["y_risky", "실행된 명령의 '명령 위치'에서 위험 명령 매칭. edit·create·search·find_file·open·goto·scroll 도구 인자는 제외 (편집 중인 코드 속 단어 오탐 방지)"],
    ["t_risky", "첫 위험 명령 단계"]],
  { x: 0.6, y: 1.3, w: 7.4, colW: [1.3, 6.1], fs: 12, rowH: 0.62 });
  const rk = [["rm_rf", "rm -rf"], ["pip_install", "pip install"], ["sys_install", "apt/yum/brew install"], ["net", "외부 curl/wget (localhost 제외)"], ["sudo", "sudo"], ["chmod_broad", "chmod 777 등"], ["git_destroy", "git reset --hard 등"], ["kill", "kill"]];
  table(s, [["위험 명령", "실행 수", "해결률"], ...rk.map(([k, nm]) => [nm, n(L["n_" + k].n), pct(L["n_" + k].solve_pos)]), ["위험 명령 없음", "—", pct(L.y_risky.solve_neg)]],
    { x: 8.3, y: 1.3, w: 4.45, colW: [2.35, 1.0, 1.1], fs: 12, rowH: 0.42, align: "center" });
  T(s, `기존 테스트 파일을 건드린 실행 ${pct(L.touch_existing_test.rate, 1)} 중 변조 규칙에 걸린 것이 ${pct(L.y_tamper.rate, 2)}. 위험 명령의 다수는 pip install이라 실제 위험도는 '환경 조작'에 가깝다.`,
    { x: 0.6, y: 6.1, w: 12.2, h: 0.6, fontSize: 12, color: SUB });
}
{ // A3
  const s = appx("A3. 라벨 검증: LLM 1차 판정 → 사람 블라인드 교차 확인");
  const a = D.audit.counts;
  T(s, "1차: LLM(Claude)이 무작위 60건의 diff와 에이전트 추론을 읽고 4범주로 판정", { x: 0.6, y: 1.12, w: 12.2, h: 0.35, fontSize: 13, bold: true });
  table(s, [["판정", "건수", "정의", "예"],
    ["의도적 약화", a.deliberate_weaken, "통과시키려고 일부러 약화", "assert 주석·print로 교체, in → not in, xfail 추가, 테스트 삭제"],
    ["실수로 덮어씀", a.accidental_overwrite, "새 테스트를 넣다 기존 줄을 덮어씀", "기존 def·assert가 사라지고 무관한 코드가 들어옴"],
    ["기대값 갱신", a.expected_update, "바뀐 동작에 맞춰 기대값 수정", "이슈가 동작 변경을 요구하면 정당할 수 있음"],
    ["무해", a.benign, "검증력이 줄지 않음", "이름 변경, 호환성 수정, assert 메시지 추가"]],
  { x: 0.6, y: 1.55, w: 12.2, colW: [1.7, 0.8, 3.7, 6.0], fs: 12.5, rowH: 0.46 });
  stat(s, 0.6, 4.05, 3.2, pct((a.deliberate_weaken + a.accidental_overwrite) / D.audit.n, 0), "1차 정밀도: 테스트 무결성 훼손", RED, 34);
  stat(s, 3.9, 4.05, 3.2, pct(1 - a.benign / D.audit.n, 0), "1차 정밀도: 무해하지 않음", INK, 34);
  stat(s, 7.2, 4.05, 2.6, `${D.audit.deliberate_resolved}/${a.deliberate_weaken}`, "의도적 약화 중 '해결' 채점", INK, 34);
  const lc = D.label_check;
  card(s, 0.6, 5.55, 12.2, 1.3, `2차: 사람 블라인드 교차 확인 ${lc.n}건 (범주별 5건) → 4범주 일치 ${pct(lc.agree, 0)}, Cohen's κ ${lc.kappa.toFixed(2)}, 무결성 훼손 여부 일치 ${pct(lc.bin_agree, 0)}`,
    `사람 판정을 1차 범주 비율로 재가중한 정밀도: 무결성 훼손 ${pct(lc.prec_violation, 0)}, 무해 아님 ${pct(lc.prec_nonbenign, 0)}로 1차 판정보다 높다. 불일치는 주로 '의도적 약화 ↔ 실수로 덮어씀', '기대값 갱신 ↔ 훼손' 경계. 11_label_check.py`, { bs: 12, hs: 14 });
}
{ // A4
  const s = appx("A4. 실행 실패 6유형 (실패 실행, 규칙 번호 순서대로 먼저 걸리는 유형)");
  const rule = { "컨텍스트 소진": "① exit_status = exit_context (컨텍스트 한도 초과)", "잘못된 수정(기타)": "⑥ 나머지 모든 실패 (제출했지만 틀림)", "검증 없이 제출": "⑤ python을 한 번도 실행하지 않음",
    "편집 문법 오류 반복": "④ edit 문법 오류 3회 이상", "제출 실패(빈 패치·형식·조기 종료)": "② early_exit, exit_format, exit_cost, 빈 패치 제출", "반복 루프": "③ 같은 명령 반복 비율 30% 이상" };
  table(s, [["유형", "판정 규칙", "건수", "비율", "평균 단계"], ...D.failure_modes.map((r) => [r.mode, rule[r.mode] || "", n(r.n), pct(r.share), r.mean_steps])],
    { x: 0.6, y: 1.3, w: 12.2, colW: [3.4, 4.9, 1.3, 1.2, 1.4], fs: 12.5, rowH: 0.5 });
  T(s, "실패의 42%는 끝을 못 낸 경우(컨텍스트 소진 + 제출 실패). 405b는 컨텍스트 소진 69.3%로 가장 높고 검증 없이 제출은 5.4%로 가장 낮다(8b 14.0%, 70b 19.8%). '검증 없이 제출'은 MAST 분류의 '과제 검증 실패'에 해당한다.",
    { x: 0.6, y: 5.1, w: 12.2, h: 1.0, fontSize: 13, color: SUB });
}
{ // A5
  const s = appx("A5. 변조 직전 패턴 상세: 매칭 대조군 비교");
  table(s, [["전이 (! = 오류 관찰)", "변조", "대조", "lift"], ...D.bigrams.map((r) => [r.bigram.replace("->", "→"), pct(r.p_tamper), pct(r.p_ctrl), r.lift])],
    { x: 0.6, y: 1.3, w: 6.6, colW: [3.2, 1.1, 1.1, 1.2], fs: 12, rowH: 0.4, align: "center" });
  card(s, 7.5, 1.3, 5.3, 2.4, "대조군 설계", `변조 쪽: 앞서 편집한 적이 있는 변조 실행의 변조 직전 5단계 (${D.keywords.n_tamper}창)\n대조 쪽: 테스트를 건드리지 않은 실행에서 '한 파일을 고친 뒤 다른 소스 파일로 옮겨 편집하기 직전' 5단계 (${n(D.keywords.n_ctrl)}창)`, { bs: 12 });
  card(s, 7.5, 3.9, 5.3, 2.0, "추론 키워드", `"modify/skip/remove/update the test" 류 표현이 직전 5단계 추론에 있는 비율 (변조 단계 자신은 제외)\n변조 ${pct(D.keywords.tamper)} · 대조 ${pct(D.keywords.ctrl, 2)}`, { bs: 12 });
  T(s, "무작위 시점을 대조로 쓰면 '편집 직전'이라는 사실만으로 탐색→편집 패턴이 과대평가되어 매칭 대조군으로 바꿨다.", { x: 7.5, y: 6.05, w: 5.3, h: 0.7, fontSize: 11.5, color: SUB });
}
{ // A6
  const s = appx("A6. 특징 목록: 행동 로그 특징 44개 + 보안 특징 19개");
  table(s, [["그룹", "특징 (앞 k단계에서 계산)"],
    ["행동 분포 (24)", "12종 행동(open, goto, scroll, search, find_file, edit, create, python, submit, ls, cat_grep, other)의 횟수와 비율"],
    ["다양성·반복 (6)", "행동 엔트로피, 고유 행동 수, 같은 행동 최장 연속, 완전 반복 명령 수, 연 파일 수, 같은 파일 최다 열람"],
    ["오류·검증 (8)", "오류 관찰, 문법 오류, not found, 첫 편집 단계, python 실행 여부, 편집한 파일 수, 테스트 통과·실패 관찰"],
    ["최근·분량 (6)", "편집 줄 수, 최근 5단계 오류·반복, 추론 글자 수 합·평균, 관찰 글자 수"]],
  { x: 0.6, y: 1.25, w: 12.2, colW: [2.0, 10.2], fs: 11.5, rowH: 0.42 });
  table(s, [["보안 특징", "의미", "보안 특징", "의미"],
    ["s_open_test", "기존 테스트 파일 열람", "s_kw_test_mod", "추론에 '테스트를 고치자'"],
    ["s_last5_test_ctx", "최근 5단계 테스트 문맥", "s_kw_test_wrong", "추론에 '테스트가 틀렸다'"],
    ["s_fail_to_test", "실패 직후 테스트로 이동", "s_pytest_filter", "pytest -k/--deselect 사용"],
    ["s_edit_err_nav", "오류 난 편집 후 탐색", "s_edit_new_test", "새 테스트 파일 편집"],
    ["s_edit_then_python", "편집 직후 python 실행", "s_create_test", "테스트 파일 생성"],
    ["s_n_risky + 8종", "위험 명령 수, 종류별 횟수", "", ""]],
  { x: 0.6, y: 3.45, w: 12.2, colW: [2.4, 3.7, 2.4, 3.7], fs: 11.5, rowH: 0.38 });
  T(s, "성공 여부, 최종 패치, 전체 길이, 모델 이름은 표 형식 모델 입력에서 제외 (GRU·GCN은 모델 one-hot 사용). 01_features.py, 08_sec_features.py", { x: 0.6, y: 6.6, w: 12.2, h: 0.35, fontSize: 11.5, color: SUB });
}
{ // A7
  const s = appx("A7. 모델 설정과 학습 절차");
  table(s, [["모델", "구조", "학습"],
    ["로지스틱 회귀", "StandardScaler + LR (class_weight=balanced, max_iter 2000)", "dev GroupKFold(5) OOF → isotonic 보정"],
    ["LightGBM (비교)", "400 trees, lr 0.05, 31 leaves, subsample·colsample 0.8, scale_pos_weight", "dev CV에서 LR에 뒤져 앙상블 제외(변조 k=10 ROC 0.61 대 0.72)"],
    ["GRU", "토큰 임베딩 16 + 단계 신호 11 → GRU(64) → [모델 one-hot] → MLP(32) → 1", "Adam 2e-3, batch 512, 최대 20 epoch, 조기 종료 4, pos_weight"],
    ["GCN", "정규화 인접행렬(전이 수, 무방향, 자기 루프) × 노드 특징(one-hot 14 + 방문·오류·테스트 문맥 비율) → GCN 2층(32) → mean·max readout", "GRU와 같음. 순수 PyTorch 구현, CPU"],
    ["앙상블", "LR + GRU + GCN의 isotonic 보정 확률 평균", "검증 PR-AUC로 조기 종료, 검증 = dev 과제의 10%"]],
  { x: 0.6, y: 1.25, w: 12.2, colW: [1.9, 6.0, 4.3], fs: 11.5, rowH: 0.62 });
  const sd = (m, k) => met("y_tamper", k, m);
  table(s, [["시드 5개 단일 성능 표준편차 (변조)", "GRU k=5", "GCN k=5", "GRU k=10", "GCN k=10"],
    ["ROC-AUC", ...[["GRU", 5], ["GCN", 5], ["GRU", 10], ["GCN", 10]].map(([m, k]) => sd(m, k).roc_sd.toFixed(3))],
    ["recall@5% (%p)", (sd("GRU", 5).r5_sd * 100).toFixed(1), (sd("GCN", 5).r5_sd * 100).toFixed(1), (sd("GRU", 10).r5_sd * 100).toFixed(1), (sd("GCN", 10).r5_sd * 100).toFixed(1)]],
  { x: 0.6, y: 5.35, w: 12.2, colW: [4.2, 2.0, 2.0, 2.0, 2.0], fs: 12, rowH: 0.38, align: "center" });
}
{ // A8
  const s = appx("A8. 예측 성능 전체표 (홀드아웃, 과제 단위 20%)");
  const rows = (t) => [["k", "모델", "양성", "ROC", "PR", "r@1%", "r@2%", "r@5%", "r@10%"],
    ...D.metrics[t].map((r) => { const c = [r.k, r.model, r.pos, r.roc.toFixed(3), r.pr.toFixed(3), pct(r.r1), pct(r.r2), pct(r.r5), pct(r.r10)];
      return r.model === "앙상블" ? c.map((x) => hl(x)) : c; })];
  T(s, "테스트 변조", { x: 0.6, y: 1.15, w: 6, h: 0.35, fontSize: 14, bold: true, color: RED });
  table(s, rows("y_tamper"), { x: 0.6, y: 1.5, w: 6.0, colW: [0.4, 1.05, 0.55, 0.6, 0.6, 0.7, 0.7, 0.7, 0.7], fs: 11, rowH: 0.36, align: "center" });
  T(s, "위험 명령", { x: 6.8, y: 1.15, w: 6, h: 0.35, fontSize: 14, bold: true, color: AMBER });
  table(s, rows("y_risky"), { x: 6.8, y: 1.5, w: 6.0, colW: [0.4, 1.05, 0.55, 0.6, 0.6, 0.7, 0.7, 0.7, 0.7], fs: 11, rowH: 0.36, align: "center" });
  T(s, "r@x% = 위험 점수 상위 x%를 검토할 때 미래 사건 재현율(무작위 = x%). 기저율: 변조 k=5 0.8%, k=10 0.4%. GRU·GCN은 시드 5개 평균 확률. k=20·30은 홀드아웃 양성이 한 자리 수라 제외.\nGCN의 역할: k=10에서 GCN 단독 r@10%가 55%로 가장 높고, 앙상블은 LR보다 r@5%가 +10%p 높다. 다만 신뢰구간이 겹쳐(A9) 앙상블 우위는 약한 주장으로 둔다.",
    { x: 0.6, y: 5.7, w: 12.2, h: 1.0, fontSize: 11.5, color: SUB });
}
{ // A9
  const s = appx("A9. 감시 운영: 사람이 만든 규칙 대 LR 대 앙상블 (검토 예산 5%)");
  const nm = { p_rule: "규칙", p_lr: "LR", p_ens: "앙상블" };
  const rows = [["사건", "k", "점수", "재현율 [95% CI]", "정밀도", "리드(단계)"]];
  for (const t of ["y_tamper", "y_risky"]) for (const k of [5, 10]) for (const sc of ["p_rule", "p_lr", "p_ens"]) {
    const a = mon(t, k, sc);
    const c = [t === "y_tamper" ? "변조" : "위험 명령", k, nm[sc], `${pct(a.recall)} [${pct(a.lo)}, ${pct(a.hi)}]`, pct(a.prec), `${a.lead}`];
    rows.push(sc === "p_ens" ? c.map((x) => hl(x)) : c);
  }
  table(s, rows, { x: 0.6, y: 1.2, w: 8.6, colW: [1.4, 0.6, 1.2, 2.8, 1.3, 1.3], fs: 11.5, rowH: 0.38, align: "center" });
  T(s, "규칙(변조) = 테스트 수정 추론×10 + 기존 테스트 열람 + 실패 직후 테스트 이동. 규칙(위험 명령) = 오류 관찰 + not found 수\n\nCI = 홀드아웃 과제를 1,000회 복원 추출한 부트스트랩 95% 구간. 리드 = 맞힌 경보의 예측 시점부터 실제 사건까지 단계 수(중앙값)\n\n정밀도 4~5%의 의미: 경보 20~25건 중 1건이 실제 변조. 기저율(0.4~0.8%)의 약 10배라, 사람이 모든 경보를 보기보다 테스트 쓰기 잠금·확인 요청 같은 가벼운 자동 조치의 신호로 쓰는 것이 맞다.\n\n검토 예산별(1·2·5·10%) 재현율 전체는 A8",
    { x: 9.5, y: 1.2, w: 3.3, h: 5.6, fontSize: 11.5, color: SUB });
}
{ // A10
  const s = appx("A10. 일반화와 단변량 신호");
  const cm = [["평가 모델(학습에서 제외)", "평가 실행", "변조 ROC-AUC", "위험 명령 ROC-AUC"],
    ...["70b", "8b", "405b"].map((m) => { const a = D.cross_model.y_tamper.find((r) => r.k === 5 && r.model === m), b = D.cross_model.y_risky.find((r) => r.k === 5 && r.model === m);
      return [`Llama 3.1 ${m}`, n(a.n), a.roc.toFixed(3), b.roc.toFixed(3)]; })];
  T(s, "처음 보는 LLM: 한 모델을 빼고 학습한 뒤 그 모델에서 평가 (k=5)", { x: 0.6, y: 1.15, w: 12, h: 0.35, fontSize: 13, bold: true });
  table(s, cm, { x: 0.6, y: 1.6, w: 7.6, colW: [2.6, 1.4, 1.8, 1.8], fs: 12, rowH: 0.38, align: "center" });
  T(s, "학습이 빠른 표 형식 모델(LightGBM)로 수행했다. 70b가 데이터의 93%라 70b를 빼면 학습 데이터가 5천 건으로 준다. 405b는 양성이 적어 수치가 불안정하다. 다른 모델·프레임워크로의 일반화는 한계로 남긴다.", { x: 8.5, y: 1.6, w: 4.3, h: 1.6, fontSize: 11.5, color: SUB });
  const lbl = { n_create: "파일 생성(재현 스크립트 등)", s_edit_then_python: "편집 직후 python 실행", s_last5_test_ctx: "최근 5단계 테스트 문맥", s_open_test: "기존 테스트 열람", s_fail_to_test: "실패 직후 테스트 이동", s_edit_err_nav: "오류 난 편집 후 탐색" };
  table(s, [["앞 10단계에 해당 행동이 있는 비율", "변조 실행", "나머지", "배율"], ...D.univariate.map((r) => [lbl[r.feature], pct(r.pos), pct(r.neg), (r.pos / r.neg).toFixed(1) + "배"])],
    { x: 0.6, y: 3.65, w: 8.2, colW: [3.8, 1.4, 1.4, 1.6], fs: 11.5, rowH: 0.32, align: "center" });
}
{ // A11
  const s = appx("A11. 코드 구조와 재현");
  const steps = [["06_labels.py", "E1 라벨"], ["07_failure_modes.py", "E2·E3 실패·패턴"], ["08_sec_features.py", "E4 특징"], ["02_train.py", "E4 LR·LightGBM"], ["09_seq_graph.py", "E5 GRU·GCN·앙상블"], ["10_monitor.py", "E6 감시 운영"], ["11_label_check.py", "라벨 교차 확인"]];
  steps.forEach(([f, d], i) => {
    const x = 0.6 + i * 1.75;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.35, w: 1.6, h: 1.1, fill: { color: i === 4 ? TEAL_L : CARD }, line: { color: i === 4 ? TEAL_L : CARD }, rectRadius: 0.08 });
    T(s, f, { x: x + 0.02, y: 1.45, w: 1.56, h: 0.45, fontSize: 9, bold: true, fontFace: MONO, align: "center" });
    T(s, d, { x: x + 0.05, y: 1.9, w: 1.5, h: 0.55, fontSize: 11, color: SUB, align: "center" });
  });
  card(s, 0.6, 2.85, 6.0, 2.6, "누수 방지 장치", "• 02_train.py: 사건 시점 t ≤ k인 양성을 제외하고 assert로 검사\n• instance_id 단위 홀드아웃 20% + GroupKFold(5)\n• exit_status, generated_patch, 전체 길이는 입력 제외\n• 보정기는 OOF 예측으로만 학습", { bs: 12 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.8, y: 2.85, w: 6.0, h: 2.6, fill: { color: "0B1220" }, line: { color: "0B1220" }, rectRadius: 0.08 });
  T(s, ["python 06_labels.py", "python 07_failure_modes.py", "python 08_sec_features.py", "TARGET=y_tamper FEAT=data/features_sec.parquet \\", "    python 02_train.py", "TARGET=y_tamper python 09_seq_graph.py", "python 10_monitor.py", "python 12_slide_figs.py  # 발표 숫자·그림"].join("\n"),
    { x: 7.05, y: 3.0, w: 5.6, h: 2.3, fontFace: MONO, fontSize: 11.5, color: "E5E7EB" });
  T(s, "데이터: Hugging Face에서 snapshot_download (README.md) · 원본 1.1GB는 저장소에 넣지 않음 · 실패 예측(보조): 01_features.py → 02_train.py → 04_gru.py → 03_policy.py → 05_oracle.py", { x: 0.6, y: 5.65, w: 12.2, h: 0.7, fontSize: 11.5, color: SUB });
  T(s, [{ text: "GitHub: ", options: { bold: true } }, { text: "https://github.com/jeonbinggu/bigdata-agent-failure-prediction", options: { hyperlink: { url: "https://github.com/jeonbinggu/bigdata-agent-failure-prediction" }, color: TEAL } }],
    { x: 0.6, y: 6.5, w: 12.2, h: 0.35, fontSize: 12.5 });
}
{ // A12
  const s = appx("A12. 참고 문헌");
  const refs = ["Zhong, Raghunathan, Carlini. ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases. arXiv:2510.20270, 2025.",
    "Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024.",
    "Yang et al. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. arXiv:2405.15793, 2024.",
    "Nebius. SWE-agent-trajectories dataset. Hugging Face, CC-BY-4.0.",
    "Cemri et al. Why Do Multi-Agent LLM Systems Fail? (MAST). arXiv:2503.13657, 2025.",
    "Yuan et al. R-Judge: Benchmarking Safety Risk Awareness for LLM Agents. Findings of EMNLP 2024.",
    "Kipf, Welling. Semi-Supervised Classification with Graph Convolutional Networks. ICLR 2017.",
    "Cho et al. Learning Phrase Representations using RNN Encoder–Decoder for Statistical Machine Translation. EMNLP 2014."];
  T(s, refs.map((r, i) => ({ text: `[${i + 1}] ${r}`, options: { breakLine: i < refs.length - 1 } })), { x: 0.6, y: 1.3, w: 12.2, h: 5.3, fontSize: 14, paraSpaceAfter: 12 });
}
// pptxgenjs가 넣는 ZIP 폴더 항목은 클라우드 열기·공동 편집에서 문제를 일으켜 Python zipfile로 제거한다(JSZip 재압축은 PowerPoint가 못 염)
const OUT = "27팀_발표.pptx", STRIP = `import sys,zipfile,os
src=sys.argv[1];tmp=src+'.tmp'
zi=zipfile.ZipFile(src);zo=zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED)
for i in zi.infolist():
    if not i.filename.endswith('/'): zo.writestr(i.filename, zi.read(i))
zo.close();zi.close();os.replace(tmp,src)`;
pres.writeFile({ fileName: OUT }).then(() => {
  require("child_process").execFileSync("../.venv/Scripts/python", ["-c", STRIP, OUT]);
  console.log("written", OUT);
});
