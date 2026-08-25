const fs = require("fs");

const html = fs.readFileSync("app/static/index.html", "utf8");
if (!html.includes("V3.2 完整策略")) throw new Error("云端必须标记V3.2完整策略");
for (const mobileRequirement of [
  'viewport-fit=cover',
  '.dashboard { order: -1;',
  '.dashboard > .actionBanner { order: -10;',
  'font-size: 16px;',
  '.plan td:nth-child(4)::before { content: "仓位"; }',
]) {
  if (!html.includes(mobileRequirement)) {
    throw new Error(`missing mobile layout protection: ${mobileRequirement}`);
  }
}
if (!html.includes('id="remainingPlan"')) {
  throw new Error("missing remaining-position plan in primary decision area");
}
if (!html.includes("卖出助手 V3.2")) {
  throw new Error("assistant version must be V3.2");
}
for (const requiredId of ["aOpeningRangeHigh", "aSecondaryBreakout", "aTailGuard"]) {
  if (!html.includes(`id="${requiredId}"`)) {
    throw new Error(`missing opening-range/tail metric: ${requiredId}`);
  }
}
if (html.includes('id="auctionRatio" type="number" step="0.1" value="0"')) {
  throw new Error("unknown auction ratio must not be rendered as a real zero");
}
if (!html.includes('id="aAuctionNote"') || !html.includes('不代表当前价')) {
  throw new Error("missing auction/frozen-quote status protection");
}
for (const requiredId of ["tdxProcess", "tdxReady", "tdxAutostart", "tdxStartBtn", "tdxStatusNote"]) {
  if (!html.includes(`id="${requiredId}"`)) {
    throw new Error(`missing TDX remote monitor element: ${requiredId}`);
  }
}
if (!html.includes('/api/tdx/status') || !html.includes('/api/tdx/start')) {
  throw new Error("TDX remote monitor endpoints are not wired into the page");
}
const match = html.match(/<script>\s*([\s\S]*?)<\/script>/);
if (!match) throw new Error("Embedded script not found");

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id,
      value: "",
      textContent: "",
      className: "",
      innerHTML: "",
      style: {},
      addEventListener() {},
    });
  }
  return elements.get(id);
}

const documentStub = {
  getElementById: element,
  querySelectorAll() {
    return [];
  },
};

const runtime = new Function(
  "document",
  "location",
  "localStorage",
  "setInterval",
  "clearInterval",
  `const window={APP_CONFIG:{}}; const history={replaceState(){}}; ${match[1]}; return { readState, decide, forecast, executableSell, answerQuestion, render, applyProfile, applyQuote, setSignalStateForTest, clearMarketState, localProfileOverrides, resolveUrlCode, inferAutomaticHaltState };`
)(
  documentStub,
  { protocol: "file:", origin: "null", search: "", hash: "", pathname: "/" },
  { getItem() { return ""; }, setItem() {}, removeItem() {} },
  () => 1,
  () => {}
);

if (runtime.resolveUrlCode("920107", "hx920107-2f9a7c4e8d1b6c30") !== "920059") {
  throw new Error("恒兴旧公网入口必须自动迁移到双英集团");
}
if (runtime.resolveUrlCode("920107", "different-token") !== "920107") {
  throw new Error("普通恒兴历史复盘入口不应被迁移");
}

if (runtime.localProfileOverrides["920165"].firstDayTradableShares !== 9605041
  || runtime.localProfileOverrides["920165"].issuePrice !== 19.26) {
  throw new Error("珈凯生物前端离线兜底资料无效");
}
if (runtime.localProfileOverrides["920138"].firstDayTradableShares !== 34613757
  || runtime.localProfileOverrides["920138"].issuePrice !== 18.86
  || !runtime.localProfileOverrides["920138"].valuationSummary.includes("48-65")) {
  throw new Error("杰理科技前端离线兜底资料无效");
}
if (runtime.localProfileOverrides["920107"].firstDayTradableShares !== 18873000
  || runtime.localProfileOverrides["920107"].issuePrice !== 16.02
  || runtime.localProfileOverrides["920107"].listingDate !== "2026-08-17"
  || !runtime.localProfileOverrides["920107"].valuationSummary.includes("42-47")) {
  throw new Error("恒兴股份前端离线兜底资料无效");
}
if (runtime.localProfileOverrides["920059"].firstDayTradableShares !== 32318326
  || runtime.localProfileOverrides["920059"].issuePrice !== 11.13
  || runtime.localProfileOverrides["920059"].listingDate !== "2026-08-19"
  || !runtime.localProfileOverrides["920059"].valuationSummary.includes("14.2-16.2")) {
  throw new Error("双英集团前端离线兜底资料无效");
}

runtime.applyProfile(runtime.localProfileOverrides["920107"], { source: "test" });
runtime.applyQuote({
  code: "920107",
  name: "恒兴股份",
  price: 30.05,
  open: 29.24,
  high: 36.28,
  low: 29.01,
  vwap: 31.11,
  turnover: 96.73,
  floatMarketValue: 567000000,
  firstDayTradableShares: 18873000,
  denominatorVerified: true,
  denominatorSource: "上市公告书",
  auctionRatio: 3.1829,
  auctionCaptured: true,
  marketPhase: "closed",
  crossChecked: true,
  dataQuality: { confidence: "high", denominatorVerified: true, tqPrimary: true },
  checkpoints: { auction_0925: { capturedAt: "2026-08-17T09:25:40.723" } },
  sessionDate: "2026-08-17",
}, {
  source: "TdxQuant+TencentCheck",
  stale: false,
  ageSeconds: 0,
  consecutiveFailures: 0,
  usingCache: false,
  updatedAt: "2026-08-17T15:36:45",
});
if (element("aTradableShares").textContent !== "1887.30 万股"
  || element("auctionRatio").value !== "3.18"
  || element("aAuction").textContent !== "3.18%"
  || element("aFreshness").textContent !== "已收盘") {
  throw new Error("live metric cards must render verified float/auction/closed state");
}

setInputs({
  code: "920107",
  name: "N恒兴复盘",
  issuePrice: 16.02,
  targetPrice: "",
  floatCap: 5.67,
  tradableSharesWan: 1887.3,
  denominatorSource: "北交所上市公告书",
  denominatorVerified: 1,
  position: 400,
  singleLotMode: "tolerance",
  industryHeat: 1,
  peDiscount: 40,
  clock: "09:42:00",
  openPrice: 29.24,
  currentPrice: 30.01,
  highPrice: 31.29,
  lowPrice: 29.01,
  vwap: 30.21,
  turnover: 35,
  turnover30: 0,
  auctionRatio: 3.18,
  auctionImbalance: 0,
  auctionBookVerified: 1,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const hengxing0942 = runtime.decide(runtime.readState());
if (!hengxing0942.firstRallyFade
  || hengxing0942.ratio !== 50
  || !hengxing0942.nearest.includes("首轮冲高回落")
  || !hengxing0942.remainingPlan.includes("31.29")) {
  throw new Error(`恒兴9:42首轮分批规则无效: ${JSON.stringify(hengxing0942)}`);
}

setInputs({
  clock: "09:45:00",
  currentPrice: 29.44,
  highPrice: 31.29,
  vwap: 30.176,
  turnover: 43,
});
runtime.decide(runtime.readState());

setInputs({
  position: 200,
  clock: "09:59:00",
  currentPrice: 32.18,
  highPrice: 32.20,
  vwap: 30.207,
  turnover: 56,
});
const hengxing0959 = runtime.decide(runtime.readState());
if (!hengxing0959.secondaryTrendHeld
  || hengxing0959.ratio !== 0
  || !hengxing0959.nearest.includes("二次突破成立")
  || hengxing0959.openingRangeSignals.secondaryBreakoutLevel !== 31.29) {
  throw new Error(`恒兴9:59二次突破规则无效: ${JSON.stringify(hengxing0959)}`);
}

setInputs({
  clock: "10:04:00",
  currentPrice: 32.50,
  highPrice: 36.28,
  vwap: 30.634,
  turnover: 63,
});
const hengxing1004 = runtime.decide(runtime.readState());
if (!hengxing1004.secondaryTailExit
  || hengxing1004.ratio !== 100
  || !hengxing1004.nearest.includes("卖出全部剩余尾仓")
  || Math.abs(hengxing1004.openingRangeSignals.tailGuard - 34.466) > 0.01) {
  throw new Error(`恒兴10:04尾仓止盈规则无效: ${JSON.stringify(hengxing1004)}`);
}

function setInputs(values) {
  for (const [key, value] of Object.entries(values)) element(key).value = String(value);
}

function setShuangyingInputs(values = {}) {
  runtime.clearMarketState(false);
  setInputs({
    code: "920059",
    name: "双英集团",
    issuePrice: 11.13,
    targetPrice: "",
    floatCap: 5,
    tradableSharesWan: 3231.8326,
    denominatorSource: "发行结果公告",
    denominatorVerified: 1,
    position: 400,
    singleLotMode: "tolerance",
    industryHeat: 0,
    peDiscount: 58.8,
    clock: "09:32:00",
    openPrice: 15,
    currentPrice: 15.10,
    highPrice: 15.20,
    lowPrice: 14.95,
    vwap: 15.05,
    turnover: 4,
    turnover30: "",
    auctionRatio: 1,
    auctionImbalance: 0,
    auctionBookVerified: 0,
    unlock: 0,
    haltState: "auto",
    notes: "",
    ...values,
  });
}

setShuangyingInputs();
const shuangyingTrim = runtime.decide(runtime.readState());
if (shuangyingTrim.ratio !== 50
  || !shuangyingTrim.nearest.includes("余仓挂15.75")
  || !shuangyingTrim.deadline.includes("09:40")) {
  throw new Error(`双英中性开盘分批规则无效: ${JSON.stringify(shuangyingTrim)}`);
}

setShuangyingInputs({position: 100});
const shuangyingSingleLot = runtime.decide(runtime.readState());
if (shuangyingSingleLot.ratio !== 0
  || !shuangyingSingleLot.nearest.includes("单手专案")
  || !shuangyingSingleLot.nearest.includes("15.75")) {
  throw new Error(`双英单手目标等待规则无效: ${JSON.stringify(shuangyingSingleLot)}`);
}

setShuangyingInputs({clock: "09:35:00", currentPrice: 15.80, highPrice: 15.80, vwap: 15.40});
const shuangyingTarget = runtime.decide(runtime.readState());
if (shuangyingTarget.ratio !== 100 || !shuangyingTarget.nearest.includes("冲高目标 15.75")) {
  throw new Error(`双英冲高目标规则无效: ${JSON.stringify(shuangyingTarget)}`);
}

setShuangyingInputs({clock: "09:40:00", currentPrice: 15.20, highPrice: 15.60, vwap: 15.25});
const shuangyingTimeStop = runtime.decide(runtime.readState());
if (shuangyingTimeStop.ratio !== 100 || !shuangyingTimeStop.nearest.includes("09:40时间止盈已到")) {
  throw new Error(`双英09:40时间止盈规则无效: ${JSON.stringify(shuangyingTimeStop)}`);
}

setShuangyingInputs({clock: "09:31:00", openPrice: 16.10, currentPrice: 16.05, highPrice: 16.15, lowPrice: 16.00, vwap: 16.07});
const shuangyingStrongOpen = runtime.decide(runtime.readState());
if (shuangyingStrongOpen.ratio === 100 || shuangyingStrongOpen.nearest.includes("16.00元强势兑现线")) {
  throw new Error(`双英16元静态清仓线仍在生效: ${JSON.stringify(shuangyingStrongOpen)}`);
}

// 2026-08-19 双英集团上午真实行情回放：9:31强势结构不得被静态估值线清仓。
setShuangyingInputs({
  position: 100,
  clock: "09:31:04",
  openPrice: 20.88,
  currentPrice: 21.99,
  highPrice: 22.00,
  lowPrice: 20.85,
  vwap: 21.19,
  turnover: 16.2,
  turnover30: 16.2,
  auctionRatio: 5.37,
  auctionImbalance: 0,
  auctionBookVerified: 1,
});
const shuangyingActual0931 = runtime.decide(runtime.readState());
if (shuangyingActual0931.ratio !== 0
  || !shuangyingActual0931.nearest.includes("超预期动量保持")
  || shuangyingActual0931.nearest.includes("16.00元")) {
  throw new Error(`双英实盘9:31不应清仓: ${JSON.stringify(shuangyingActual0931)}`);
}

// 第一次临停：冻结09:40时限，行情静止不得误报数据异常。
setShuangyingInputs({
  position: 100,
  clock: "09:40:00",
  openPrice: 20.88,
  currentPrice: 27.15,
  highPrice: 27.15,
  lowPrice: 20.85,
  vwap: 22.96,
  turnover: 35.9,
  turnover30: 35.9,
  auctionRatio: 5.37,
  auctionBookVerified: 1,
});
const shuangyingFirstHalt = runtime.decide({
  ...runtime.readState(),
  dataFresh: false,
  quoteFrozen: true,
  unchangedSeconds: 20,
});
if (shuangyingFirstHalt.haltState !== "halted30"
  || shuangyingFirstHalt.ratio !== 0
  || shuangyingFirstHalt.grade === "数据异常"
  || !shuangyingFirstHalt.nearest.includes("临停中")) {
  throw new Error(`双英第一次临停冻结规则无效: ${JSON.stringify(shuangyingFirstHalt)}`);
}

// 多手仓位在第一次临停复牌后的有效交易区只先兑现一半。
setShuangyingInputs({
  position: 400,
  clock: "09:46:45",
  openPrice: 20.88,
  currentPrice: 27.40,
  highPrice: 27.50,
  lowPrice: 20.85,
  vwap: 23.21,
  turnover: 38.2,
  turnover30: 38.2,
  auctionRatio: 5.37,
  auctionBookVerified: 1,
});
const shuangyingFirstHaltTrim = runtime.decide(runtime.readState());
if (shuangyingFirstHaltTrim.ratio !== 50 || !shuangyingFirstHaltTrim.nearest.includes("第一次临停区")) {
  throw new Error(`双英第一次临停多手分批规则无效: ${JSON.stringify(shuangyingFirstHaltTrim)}`);
}

// 第二次临停自动识别，复牌大幅回撤后100股在首个可成交盘口退出。
setShuangyingInputs({
  position: 100,
  clock: "09:51:00",
  openPrice: 20.88,
  currentPrice: 33.41,
  highPrice: 33.41,
  lowPrice: 20.85,
  vwap: 24.36,
  turnover: 44.9,
  turnover30: 44.9,
  auctionRatio: 5.37,
  auctionBookVerified: 1,
});
const shuangyingSecondHalt = runtime.decide({
  ...runtime.readState(),
  dataFresh: false,
  quoteFrozen: true,
  unchangedSeconds: 20,
});
if (shuangyingSecondHalt.haltState !== "halted60"
  || shuangyingSecondHalt.ratio !== 0
  || shuangyingSecondHalt.grade === "数据异常") {
  throw new Error(`双英第二次临停识别无效: ${JSON.stringify(shuangyingSecondHalt)}`);
}
setInputs({clock:"10:05:56", currentPrice:27.18, highPrice:33.50, vwap:25.58, turnover:60.4, turnover30:44.9});
const shuangyingPostSecondHalt = runtime.decide({
  ...runtime.readState(),
  dataFresh: true,
  quoteFrozen: false,
  unchangedSeconds: 0,
});
if (shuangyingPostSecondHalt.ratio !== 100
  || !shuangyingPostSecondHalt.nearest.includes("第二次临停后峰值回撤")) {
  throw new Error(`双英第二次临停复牌退出规则无效: ${JSON.stringify(shuangyingPostSecondHalt)}`);
}

runtime.clearMarketState(false);

function run(name, values, expectedType, expectedText) {
  setInputs({
    code: "920000",
    name: name,
    issuePrice: 10,
    targetPrice: "",
    floatCap: 6,
    tradableSharesWan: 1000,
    denominatorSource: "测试上市公告",
    denominatorVerified: 1,
    position: 300,
    singleLotMode: "tolerance",
    industryHeat: 1,
    peDiscount: "",
    clock: "09:35:00",
    openPrice: 20,
    currentPrice: 21,
    highPrice: 22,
    lowPrice: 19,
    vwap: 20.5,
    turnover: 40,
    turnover30: 20,
    auctionRatio: 2,
    auctionImbalance: 0,
    auctionBookVerified: 0,
    unlock: 0,
    haltState: "auto",
    notes: "",
    ...values,
  });
  const decision = runtime.decide(runtime.readState());
  const prediction = runtime.forecast(runtime.readState());
  if (decision.type !== expectedType) {
    throw new Error(`${name}: expected ${expectedType}, got ${decision.type}`);
  }
  if (!decision.nearest.includes(expectedText)) {
    throw new Error(`${name}: expected "${expectedText}", got "${decision.nearest}"`);
  }
  if (!prediction || prediction.low.mid > prediction.high.mid) {
    throw new Error(`${name}: invalid forecast range`);
  }
  if (!decision.bestWindow) {
    throw new Error(`${name}: missing model sell window`);
  }
  if (decision.ratio <= 0 && ["减仓", "卖出", "强风险"].includes(decision.grade)) {
    throw new Error(`${name}: non-executable action must not use an executable grade: ${decision.grade}`);
  }
  if (decision.ratio > 0 && decision.grade === "观察") {
    throw new Error(`${name}: executable action must not remain in observe grade`);
  }
  if (prediction.high.high < Number(element("highPrice").value)) {
    throw new Error(`${name}: forecast high is below observed high`);
  }
  console.log(`${name}: ${decision.type} / ${decision.nearest}`);
}

run("极端高开", { openPrice: 45, currentPrice: 47, highPrice: 48, vwap: 46, floatCap: 4 }, "A", "换手与价格结构共振向上");
run("中等热度", { openPrice: 25, currentPrice: 26, highPrice: 27, vwap: 25.5, floatCap: 7 }, "B", "换手与价格结构共振向上");
run("温和走势", { openPrice: 18, currentPrice: 19, highPrice: 19.5, vwap: 18.8, floatCap: 12 }, "C", "生命线");
run("开盘破发", { openPrice: 9.5, currentPrice: 9.3, highPrice: 9.5, vwap: 9.4 }, "D", "破发");

setInputs({
  code: "920038",
  name: "森合高科",
  issuePrice: 29.06,
  floatCap: 9.93,
  tradableSharesWan: 3416.6081,
  denominatorSource: "北交所上市公告书",
  denominatorVerified: 1,
  position: 100,
  industryHeat: 1,
  peDiscount: 61.25,
  clock: "09:20:00",
  openPrice: "",
  currentPrice: "",
  highPrice: "",
  lowPrice: "",
  vwap: "",
  turnover: "",
  turnover30: "",
  auctionRatio: 0,
  unlock: 1,
  haltState: "auto",
  notes: "",
});
const senheForecast = runtime.forecast(runtime.readState());
const senhePlan = runtime.decide(runtime.readState()).plan;
if (!senheForecast
  || senheForecast.open.low !== 42
  || senheForecast.open.mid !== 55
  || senheForecast.open.high !== 62
  || senheForecast.high.high < 68
  || !senhePlan.some(row => row[0] === "估值观察档" && row[2] === 48)) {
  throw new Error(`森合高科预案无效: ${JSON.stringify(senheForecast)} / ${JSON.stringify(senhePlan)}`);
}

setInputs({
  code: "920165",
  name: "珈凯生物",
  issuePrice: 19.26,
  targetPrice: "",
  floatCap: "",
  tradableSharesWan: 960.5041,
  denominatorSource: "北交所上市公告书",
  denominatorVerified: 1,
  industryHeat: 2,
  peDiscount: 48.8,
  unlock: 1,
  openPrice: "",
  currentPrice: "",
  highPrice: "",
  lowPrice: "",
  vwap: "",
  turnover: "",
  turnover30: "",
  auctionRatio: 0,
  clock: "09:25:00",
  notes: "",
});
const jiakaiForecast = runtime.forecast(runtime.readState());
const jiakaiPremarket = runtime.decide(runtime.readState());
if (!jiakaiForecast
  || jiakaiForecast.open.low !== 44
  || jiakaiForecast.open.high !== 53
  || jiakaiForecast.low.low !== 34
  || jiakaiForecast.low.high !== 43
  || jiakaiForecast.high.low !== 50
  || jiakaiForecast.high.high !== 80
  || !jiakaiPremarket.reasons.some(item => item.text.includes("老股308.8003万股"))) {
  throw new Error(`珈凯生物盘前预案无效: ${JSON.stringify(jiakaiForecast)} / ${JSON.stringify(jiakaiPremarket.reasons)}`);
}

setInputs({
  openPrice: 55,
  currentPrice: 62,
  highPrice: 62,
  lowPrice: 54.8,
  vwap: 59.5,
  turnover: 35.6,
  clock: "09:40:00",
});
const jiakaiStrongAt62 = runtime.decide(runtime.readState());
if (jiakaiStrongAt62.ratio !== 0
  || jiakaiStrongAt62.targetSignals.configured
  || !jiakaiStrongAt62.reasons.some(item => item.text.includes("高换手不作为卖出理由"))) {
  throw new Error(`珈凯生物62元强承接不得机械清仓: ${JSON.stringify(jiakaiStrongAt62)}`);
}

run("临停前", { openPrice: 20, currentPrice: 25.85, highPrice: 25.85, vwap: 24, floatCap: 7 }, "B", "临停");
const nearHaltDecision = runtime.decide(runtime.readState());
if (nearHaltDecision.ratio !== 0 || !nearHaltDecision.nearest.includes("不抢跑清仓")) {
  throw new Error(`near halt must preserve position: ${nearHaltDecision.nearest} / ${nearHaltDecision.ratio}`);
}
run("临停中", { openPrice: 20, currentPrice: 26, highPrice: 26, vwap: 24, floatCap: 7, haltState: "halted30" }, "B", "暂停普通提示");
run("开盘55强承接保护", {
  issuePrice: 8.5,
  openPrice: 55,
  currentPrice: 55,
  highPrice: 55,
  lowPrice: 55,
  vwap: 55,
  floatCap: 6,
  clock: "09:30:00"
}, "B", "暂不卖");

setInputs({
  code: "920138",
  name: "N杰理9:49复盘",
  issuePrice: 18.86,
  targetPrice: "",
  floatCap: 18.44,
  tradableSharesWan: 3461.3757,
  denominatorSource: "北交所上市公告书",
  denominatorVerified: 1,
  position: 1000,
  singleLotMode: "tolerance",
  industryHeat: 2,
  peDiscount: 50,
  clock: "09:49:00",
  openPrice: 53.00,
  currentPrice: 54.82,
  highPrice: 59.54,
  lowPrice: 52.50,
  vwap: 55.03,
  turnover: 45,
  turnover30: 0,
  auctionRatio: 2,
  auctionImbalance: 0,
  auctionBookVerified: 0,
  unlock: 1,
  haltState: "auto",
  notes: "",
});
const jieli0949 = runtime.decide(runtime.readState());
if (!jieli0949.openingSpikeFade
  || jieli0949.ratio !== 70
  || !jieli0949.nearest.includes("开盘尖峰回落")
  || !jieli0949.remainingPlan.includes("保留30%")
  || !jieli0949.remainingPlan.includes("3分钟不能站稳VWAP")) {
  throw new Error(`杰理科技9:49分批止盈规则无效: ${JSON.stringify(jieli0949)}`);
}

setInputs({position: 100});
const jieli0949SingleLot = runtime.decide(runtime.readState());
if (jieli0949SingleLot.ratio !== 100
  || !jieli0949SingleLot.nearest.includes("单手硬退出确认")
  || !jieli0949SingleLot.remainingPlan.includes("全部仓位")) {
  throw new Error(`杰理科技9:49单手退出规则无效: ${JSON.stringify(jieli0949SingleLot)}`);
}

setInputs({
  code: "920258",
  name: "N聚仁竞价预案测试",
  issuePrice: 4.48,
  floatCap: 6.84,
  tradableSharesWan: 3600,
  denominatorSource: "测试上市公告",
  denominatorVerified: 1,
  position: 400,
  industryHeat: 1,
  peDiscount: 50.4,
  clock: "09:25:30",
  openPrice: 19.00,
  currentPrice: 19.00,
  highPrice: 19.00,
  lowPrice: 19.00,
  vwap: 0,
  turnover: 3.6058,
  turnover30: 0,
  auctionRatio: 3.6058,
  auctionImbalance: -35,
  auctionBookVerified: 1,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const auctionPreplan = runtime.decide(runtime.readState());
if (auctionPreplan.ratio !== 0
  || !auctionPreplan.nearest.includes("准备开盘兑现30%")
  || !auctionPreplan.auctionOpeningSetup.eligible) {
  throw new Error(`auction preplan invalid: ${JSON.stringify(auctionPreplan)}`);
}

setInputs({clock: "09:30:10", currentPrice: 19.00, highPrice: 19.00, lowPrice: 19.00});
const auctionOpenConfirmed = runtime.decide(runtime.readState());
if (auctionOpenConfirmed.ratio !== 30
  || !auctionOpenConfirmed.nearest.includes("9:30预案确认")
  || auctionOpenConfirmed.grade === "观察"
  || auctionOpenConfirmed.reasons.some(item => item.text.includes("暂不触发卖出"))) {
  throw new Error(`auction opening confirmation invalid: ${JSON.stringify(auctionOpenConfirmed)}`);
}

setInputs({clock: "09:30:20", currentPrice: 19.30, highPrice: 19.30, lowPrice: 19.00});
const auctionOpenCancelled = runtime.decide(runtime.readState());
if (auctionOpenCancelled.ratio !== 0
  || !auctionOpenCancelled.nearest.includes("预案已取消")) {
  throw new Error(`auction opening cancellation invalid: ${JSON.stringify(auctionOpenCancelled)}`);
}

setInputs({clock: "09:30:10", currentPrice: 19.00, highPrice: 19.00, auctionImbalance: 35});
const neutralTurnoverBuyBook = runtime.decide(runtime.readState());
if (neutralTurnoverBuyBook.ratio !== 0
  || neutralTurnoverBuyBook.auctionOpeningSetup.eligible) {
  throw new Error(`sub-5 turnover must not sell without bearish book: ${JSON.stringify(neutralTurnoverBuyBook)}`);
}

setInputs({auctionImbalance: -35, auctionBookVerified: 0});
const unverifiedAuctionBook = runtime.decide(runtime.readState());
if (unverifiedAuctionBook.ratio !== 0
  || unverifiedAuctionBook.auctionOpeningSetup.dataReady) {
  throw new Error(`unverified auction book must not trigger: ${JSON.stringify(unverifiedAuctionBook)}`);
}

setInputs({
  position: 100,
  singleLotMode: "tolerance",
  auctionBookVerified: 1,
  clock: "09:30:10",
  currentPrice: 19.00,
  highPrice: 19.00,
});
const singleLotToleranceAuction = runtime.decide(runtime.readState());
if (singleLotToleranceAuction.ratio !== 0
  || !singleLotToleranceAuction.nearest.includes("单手仓位无法分批")) {
  throw new Error(`single-lot tolerance mode invalid: ${JSON.stringify(singleLotToleranceAuction)}`);
}

setInputs({singleLotMode: "return"});
const singleLotReturnAuction = runtime.decide(runtime.readState());
if (singleLotReturnAuction.ratio !== 100
  || !singleLotReturnAuction.nearest.includes("单手收益优先确认")
  || !singleLotReturnAuction.reasons.some(item => item.text.includes("30%预案转换为全部卖出"))) {
  throw new Error(`single-lot return mode invalid: ${JSON.stringify(singleLotReturnAuction)}`);
}

setInputs({auctionBookVerified: 0});
const singleLotReturnUnverified = runtime.decide(runtime.readState());
if (singleLotReturnUnverified.ratio !== 0) {
  throw new Error(`single-lot return mode must respect data gate: ${JSON.stringify(singleLotReturnUnverified)}`);
}
setInputs({singleLotMode: "tolerance"});

setInputs({
  code: "920176",
  name: "N维琪开盘急跌复盘",
  issuePrice: 22.16,
  floatCap: 12.32,
  position: 300,
  industryHeat: 2,
  peDiscount: 50,
  clock: "09:31:00",
  openPrice: 45.01,
  currentPrice: 42.00,
  highPrice: 45.01,
  lowPrice: 40.25,
  vwap: 43.00,
  turnover: 5,
  turnover30: 0,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const weiqiOpeningDip = runtime.decide(runtime.readState());
if (weiqiOpeningDip.ratio !== 0
  || weiqiOpeningDip.grade !== "观察"
  || !weiqiOpeningDip.openingActionLocked
  || Number.isFinite(weiqiOpeningDip.sellPrice)
  || !weiqiOpeningDip.nearest.includes("硬保护期内暂不卖")) {
  throw new Error(`weiqi opening lock invalid: ${JSON.stringify(weiqiOpeningDip)}`);
}

setInputs({position: 100});
const weiqiSingleLotDip = runtime.decide(runtime.readState());
if (weiqiSingleLotDip.ratio !== 0 || weiqiSingleLotDip.grade !== "观察") {
  throw new Error(`weiqi single-lot opening lock invalid: ${JSON.stringify(weiqiSingleLotDip)}`);
}

setInputs({
  position: 300,
  clock: "09:36:00",
  currentPrice: 46.00,
  highPrice: 48.00,
  vwap: 44.00,
});
const weiqiRecovered = runtime.decide(runtime.readState());
if (weiqiRecovered.ratio !== 0 || weiqiRecovered.grade === "卖出" || weiqiRecovered.grade === "强风险") {
  throw new Error(`weiqi recovery handling invalid: ${JSON.stringify(weiqiRecovered)}`);
}

setInputs({
  code: "920177",
  name: "小流通高开弱势待确认",
  issuePrice: 10,
  floatCap: 4,
  position: 300,
  industryHeat: 1,
  peDiscount: 30,
  clock: "09:36:00",
  openPrice: 55,
  currentPrice: 52,
  highPrice: 56,
  lowPrice: 51,
  vwap: 53,
  turnover: 12,
  turnover30: 0,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const smallFloatOpeningWeakness = runtime.decide(runtime.readState());
if (smallFloatOpeningWeakness.type !== "A"
  || smallFloatOpeningWeakness.ratio !== 0
  || !smallFloatOpeningWeakness.nearest.includes("尚未持续确认")
  || smallFloatOpeningWeakness.grade === "卖出") {
  throw new Error(`small-float opening weakness invalid: ${JSON.stringify(smallFloatOpeningWeakness)}`);
}

setInputs({
  code: "920176",
  name: "N维琪开盘急跌复盘",
  issuePrice: 22.16,
  floatCap: 12.32,
  position: 300,
  openPrice: 45.01,
  lowPrice: 40.25,
  auctionRatio: 3,
  haltState: "auto",
});
setInputs({
  clock: "09:41:00",
  currentPrice: 41.00,
  highPrice: 48.00,
  vwap: 43.00,
});
runtime.setSignalStateForTest({
  vwapBelowSince: Date.now() - 6 * 60 * 1000,
});
const weiqiWeaknessConfirmed = runtime.decide(runtime.readState());
if (weiqiWeaknessConfirmed.ratio !== 100
  || !weiqiWeaknessConfirmed.nearest.includes("硬退出")) {
  throw new Error(`weiqi confirmed weakness invalid: ${JSON.stringify(weiqiWeaknessConfirmed)}`);
}

setInputs({
  code: "920258",
  name: "N聚仁首分钟复盘",
  issuePrice: 4.48,
  floatCap: 6.84,
  tradableSharesWan: 3600,
  denominatorSource: "行情自动交叉核验",
  denominatorVerified: 1,
  position: 400,
  industryHeat: 1,
  peDiscount: 50.4,
  clock: "09:31:00",
  openPrice: 19.00,
  currentPrice: 18.00,
  highPrice: 19.68,
  lowPrice: 18.00,
  vwap: 19.0584,
  turnover: 13.02,
  turnover30: 13.02,
  auctionRatio: 3.6058,
  auctionImbalance: 0,
  auctionBookVerified: 0,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const jurenFirstMinute = runtime.decide(runtime.readState());
if (jurenFirstMinute.ratio !== 50
  || jurenFirstMinute.openingActionLocked
  || !jurenFirstMinute.nearest.includes("首分钟承接失败")) {
  throw new Error(`juren first-minute failure invalid: ${JSON.stringify(jurenFirstMinute)}`);
}

setInputs({
  clock: "09:35:00",
  currentPrice: 18.08,
  highPrice: 19.68,
  lowPrice: 17.00,
  vwap: 18.6285,
  turnover: 23.1586,
  turnover30: 23.1586,
});
const jurenFiveMinute = runtime.decide(runtime.readState());
if (jurenFiveMinute.ratio !== 100
  || !jurenFiveMinute.nearest.includes("极端高开承接失败")) {
  throw new Error(`juren five-minute exit invalid: ${JSON.stringify(jurenFiveMinute)}`);
}

setInputs({
  clock: "10:00:00",
  currentPrice: 17.38,
  highPrice: 19.68,
  lowPrice: 17.15,
  vwap: 18.3600,
  turnover: 42.0022,
  turnover30: 42.0022,
});
const jurenThirtyMinute = runtime.decide(runtime.readState());
if (jurenThirtyMinute.ratio !== 100
  || !jurenThirtyMinute.reasons.some(item => item.text.includes("不再等待换手率"))) {
  throw new Error(`juren price-priority exit invalid: ${JSON.stringify(jurenThirtyMinute)}`);
}

setInputs({
  clock: "10:05:00",
  currentPrice: 60.00,
  highPrice: 72.02,
  vwap: 65.00,
  haltState: "resumed30",
});
const weiqiResumeWarmup = runtime.decide(runtime.readState());
if (weiqiResumeWarmup.ratio !== 0 || weiqiResumeWarmup.grade === "卖出") {
  throw new Error(`weiqi post-halt warmup invalid: ${JSON.stringify(weiqiResumeWarmup)}`);
}

setInputs({
  code: "920065",
  name: "N千岸09:32复盘",
  issuePrice: 24.30,
  floatCap: 9.14,
  position: 100,
  industryHeat: 1,
  peDiscount: "",
  clock: "09:32:00",
  openPrice: 50.00,
  currentPrice: 55.00,
  highPrice: 55.00,
  lowPrice: 49.60,
  vwap: 52.50,
  turnover: 10,
  turnover30: 0,
  auctionRatio: 2,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const qianan0932 = runtime.decide(runtime.readState());
if (qianan0932.ratio !== 0
  || !qianan0932.openingActionLocked
  || qianan0932.grade !== "观察"
  || !qianan0932.nearest.includes("硬保护期内暂不卖")) {
  throw new Error(`qianan 09:32 protection invalid: ${JSON.stringify(qianan0932)}`);
}

setInputs({
  clock: "09:36:00",
  currentPrice: 65.00,
  highPrice: 65.00,
  vwap: 58.00,
  turnover: 35,
});
const qiananStrong = runtime.decide(runtime.readState());
if (qiananStrong.ratio !== 0
  || qiananStrong.turnoverStructure.key !== "strong"
  || !qiananStrong.nearest.includes("换手与价格结构共振向上")) {
  throw new Error(`qianan strong structure invalid: ${JSON.stringify(qiananStrong)}`);
}

setInputs({
  clock: "10:30:00",
  currentPrice: 65.00,
  highPrice: 100.00,
  vwap: 70.00,
  turnover: 70,
});
runtime.setSignalStateForTest({
  vwapBelowSince: Date.now() - 6 * 60 * 1000,
  vwapReboundFailedAt: Date.now() - 60 * 1000,
  vwapTriggerPrice: 72.00,
  vwapTriggerAt: Date.now() - 6 * 60 * 1000,
});
const qiananConfirmedExit = runtime.decide(runtime.readState());
if (qiananConfirmedExit.ratio !== 100
  || !qiananConfirmedExit.nearest.includes("单手硬退出确认")
  || qiananConfirmedExit.turnoverStructure.key === "strong"
  || qiananConfirmedExit.vwapSignals.triggerPrice !== 72) {
  throw new Error(`qianan confirmed exit invalid: ${JSON.stringify(qiananConfirmedExit)}`);
}
runtime.render();
if (!element("actionTitle").textContent.includes("卖出 100 股")
  || !element("actionPrice").textContent.includes("¥")
  || !element("actionBanner").className.includes("actionSell")) {
  throw new Error(`sell action banner is not explicit: ${element("actionTitle").textContent} / ${element("actionPrice").textContent} / ${element("actionBanner").className}`);
}
if (!element("aTurnoverStructure").textContent
  || !element("planBody").innerHTML.includes("软信号0股，硬确认后100股")
  || !element("planBody").innerHTML.includes("动态预警，不是委托价")
  || !element("planBody").innerHTML.includes("首次失守VWAP 72.00 已冻结")
  || element("planBody").innerHTML.includes("40% / 100股")) {
  throw new Error(`single-lot render invalid: ${element("aTurnoverStructure").textContent} / ${element("planBody").innerHTML}`);
}

run("午间休市", {
  openPrice: 25,
  currentPrice: 26,
  highPrice: 27,
  lowPrice: 24,
  vwap: 25.5,
  floatCap: 7,
  clock: "12:00:00"
}, "B", "午间休市");
run("14点午后观察", {
  openPrice: 25,
  currentPrice: 26.5,
  highPrice: 27,
  lowPrice: 24,
  vwap: 25.5,
  floatCap: 7,
  clock: "14:14:00"
}, "B", "午后观察");

run("14点35首日分批退出", {
  openPrice: 25,
  currentPrice: 29,
  highPrice: 29.2,
  lowPrice: 25,
  vwap: 27.5,
  floatCap: 7,
  position: 500,
  clock: "14:35:00"
}, "B", "先卖出至少50%");
const dayOneFirstExit = runtime.decide(runtime.readState());
if (dayOneFirstExit.ratio < 50) {
  throw new Error(`day-one 14:35 exit invalid: ${dayOneFirstExit.nearest} / ${dayOneFirstExit.ratio}`);
}

setInputs({position: 100});
const dayOneSingleLotExit = runtime.decide(runtime.readState());
if (dayOneSingleLotExit.ratio !== 100
  || !dayOneSingleLotExit.nearest.includes("单手硬退出确认")) {
  throw new Error(`day-one single-lot exit invalid: ${dayOneSingleLotExit.nearest} / ${dayOneSingleLotExit.ratio}`);
}

run("14点47首日全部退出", {
  openPrice: 25,
  currentPrice: 30,
  highPrice: 30.2,
  lowPrice: 25,
  vwap: 28,
  floatCap: 7,
  position: 500,
  clock: "14:47:00"
}, "B", "全部剩余仓位");
const dayOneFinalExit = runtime.decide(runtime.readState());
if (dayOneFinalExit.ratio !== 100) {
  throw new Error(`day-one final exit invalid: ${dayOneFinalExit.nearest} / ${dayOneFinalExit.ratio}`);
}

setInputs({
  code: "920079",
  name: "乔路铭开盘复盘",
  issuePrice: 12.5,
  floatCap: 12,
  position: 100,
  industryHeat: 1,
  peDiscount: "",
  clock: "09:33:00",
  openPrice: 15.80,
  currentPrice: 17.00,
  highPrice: 17.20,
  lowPrice: 15.80,
  vwap: 16.40,
  turnover: 18,
  turnover30: 0,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const qiaolumingOpen = runtime.decide(runtime.readState());
if (qiaolumingOpen.ratio !== 0 || !qiaolumingOpen.nearest.includes("硬保护期内暂不卖")) {
  throw new Error(`qiaoluming opening protection invalid: ${qiaolumingOpen.nearest} / ${qiaolumingOpen.ratio}`);
}

setInputs({
  code: "920238",
  name: "长鹰首根5分钟前",
  issuePrice: 18.89,
  floatCap: 10.87,
  position: 100,
  industryHeat: 1,
  peDiscount: "",
  clock: "09:34:00",
  openPrice: 69.00,
  currentPrice: 62.00,
  highPrice: 71.00,
  lowPrice: 61.80,
  vwap: 66.00,
  turnover: 20,
  turnover30: 0,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const changyingBeforeConfirm = runtime.decide(runtime.readState());
if (changyingBeforeConfirm.ratio !== 0 || !changyingBeforeConfirm.nearest.includes("单手仓位无法分批")) {
  throw new Error(`changying pre-confirmation invalid: ${changyingBeforeConfirm.nearest} / ${changyingBeforeConfirm.ratio}`);
}

setInputs({clock: "09:35:00"});
const changyingHardExit = runtime.decide(runtime.readState());
if (changyingHardExit.ratio !== 100 || !changyingHardExit.nearest.includes("极端高开承接失败")) {
  throw new Error(`changying hard exit invalid: ${changyingHardExit.nearest} / ${changyingHardExit.ratio}`);
}

setInputs({
  code: "920080",
  name: "单手软信号保护",
  issuePrice: 10,
  floatCap: 7,
  position: 100,
  industryHeat: 1,
  peDiscount: "",
  clock: "09:40:00",
  openPrice: 25,
  currentPrice: 26,
  highPrice: 27,
  lowPrice: 25,
  vwap: 25.5,
  turnover: 20,
  turnover30: 0,
  auctionRatio: 2,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const singleLotProtected = runtime.decide(runtime.readState());
if (singleLotProtected.ratio !== 0
  || singleLotProtected.turnoverStructure.key !== "strong"
  || !singleLotProtected.nearest.includes("换手与价格结构共振向上")) {
  throw new Error(`single-lot soft signal must not become a full exit: ${singleLotProtected.nearest} / ${singleLotProtected.ratio}`);
}

run("吉和昌竞价强承接", {
  issuePrice: 8.52,
  openPrice: 55,
  currentPrice: 61,
  highPrice: 62,
  lowPrice: 55,
  vwap: 59,
  auctionRatio: 7.36,
  floatCap: 15.38,
  clock: "09:36:00"
}, "B", "换手与价格结构共振向上");

run("高竞价开盘急跌保护", {
  issuePrice: 8.52,
  openPrice: 55,
  currentPrice: 52.8,
  highPrice: 56,
  lowPrice: 52.8,
  vwap: 54.5,
  auctionRatio: 7.36,
  floatCap: 15.38,
  clock: "09:33:00"
}, "B", "硬保护期内暂不卖");

run("高竞价换手后确认兑现", {
  issuePrice: 8.52,
  openPrice: 55,
  currentPrice: 52.8,
  highPrice: 56,
  lowPrice: 52.8,
  vwap: 54.5,
  auctionRatio: 7.36,
  floatCap: 15.38,
  clock: "09:36:00"
}, "B", "竞价巨量兑现");

run("午盘前强势不强制卖出", {
  issuePrice: 8.52,
  openPrice: 55,
  currentPrice: 67.8,
  highPrice: 69,
  lowPrice: 55,
  vwap: 61,
  auctionRatio: 7.36,
  floatCap: 15.38,
  clock: "11:27:00"
}, "B", "保留仓位午后重评");

const dynamicPlan = runtime.decide(runtime.readState()).plan;
const movingGuard = dynamicPlan.find(row => row[0] === "有效转弱档");
if (!movingGuard || Math.abs(movingGuard[2] - 65.55) > 0.01) {
  throw new Error(`dynamic trailing guard invalid: ${JSON.stringify(movingGuard)}`);
}

setInputs({
  code: "920189",
  name: "康美特",
  issuePrice: 8.14,
  floatCap: 10,
  position: 100,
  industryHeat: 2,
  peDiscount: 74.5,
  clock: "09:20:00",
  openPrice: "",
  currentPrice: "",
  highPrice: "",
  lowPrice: "",
  vwap: "",
  turnover: "",
  turnover30: "",
  auctionRatio: "",
  unlock: 1,
  haltState: "auto",
  notes: "",
});
const kmtForecast = runtime.forecast(runtime.readState());
if (!kmtForecast || kmtForecast.open.low !== 34 || kmtForecast.open.high !== 44 || kmtForecast.high.high < 54) {
  throw new Error(`kmt forecast bands invalid: ${JSON.stringify(kmtForecast)}`);
}

setInputs({
  code: "920189",
  name: "康美特",
  issuePrice: 8.14,
  floatCap: 10,
  position: 300,
  industryHeat: 2,
  peDiscount: 74.5,
  clock: "09:36:00",
  openPrice: 46,
  currentPrice: 48,
  highPrice: 49,
  lowPrice: 46,
  vwap: 47,
  turnover: 25,
  turnover30: 15,
  auctionRatio: 6,
  unlock: 1,
  haltState: "auto",
  notes: "",
});
const kmtDecision = runtime.decide(runtime.readState());
if (!kmtDecision.plan.some(row => row[0] === "估值观察档")
  || kmtDecision.ratio !== 0
  || !kmtDecision.reasons.some(row => row.text.includes("45元以上"))) {
  throw new Error(`kmt hot plan invalid: ${JSON.stringify(kmtDecision.plan)} / ${JSON.stringify(kmtDecision.reasons)}`);
}

setInputs({
  code: "920189",
  name: "康美特",
  issuePrice: 8.14,
  floatCap: 10,
  position: 300,
  industryHeat: 2,
  peDiscount: 74.5,
  clock: "09:40:00",
  openPrice: 51,
  currentPrice: 49.8,
  highPrice: 53,
  lowPrice: 49.8,
  vwap: 50.8,
  turnover: 18,
  turnover30: 12,
  auctionRatio: 6,
  unlock: 1,
  haltState: "auto",
  notes: "",
});
const kmtStall = runtime.decide(runtime.readState());
const kmtGuard = kmtStall.plan.find(row => row[0] === "有效转弱档");
if (!kmtStall.nearest.includes("高开滞涨") || !kmtGuard || Math.abs(kmtGuard[2] - 51.41) > 0.02) {
  throw new Error(`kmt stall handling invalid: ${kmtStall.nearest} / ${JSON.stringify(kmtGuard)}`);
}

setInputs({
  code: "920136",
  name: "永励精密",
  issuePrice: 19.28,
  floatCap: 7.14,
  position: 300,
  industryHeat: 1,
  peDiscount: 30,
  clock: "09:45:00",
  openPrice: 34,
  currentPrice: 34.8,
  highPrice: 35.2,
  lowPrice: 34,
  vwap: 34.5,
  turnover: 12,
  turnover30: 8,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const ylProtected = runtime.decide(runtime.readState());
if (!ylProtected.nearest.includes("低预期开盘守住") || ylProtected.ratio !== 0) {
  throw new Error(`yl protected open invalid: ${ylProtected.nearest} / ${ylProtected.ratio}`);
}

setInputs({
  code: "920136",
  name: "永励精密",
  issuePrice: 19.28,
  floatCap: 7.14,
  position: 300,
  industryHeat: 1,
  peDiscount: 30,
  clock: "11:25:00",
  openPrice: 34,
  currentPrice: 36.9,
  highPrice: 39.66,
  lowPrice: 34,
  vwap: 37.2,
  turnover: 55,
  turnover30: 35,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const ylPulse = runtime.decide(runtime.readState());
if (!ylPulse.nearest.includes("上午脉冲结束") || ylPulse.ratio < 50) {
  throw new Error(`yl pulse fade invalid: ${ylPulse.nearest} / ${ylPulse.ratio}`);
}

setInputs({
  code: "920117",
  name: "龙鑫智能",
  issuePrice: 17.83,
  floatCap: 7.14,
  position: 300,
  industryHeat: 2,
  peDiscount: "",
  clock: "14:45:00",
  openPrice: 36.50,
  currentPrice: 35.34,
  highPrice: 40.60,
  lowPrice: 35.20,
  vwap: 37.66,
  turnover: 93.18,
  turnover30: 8,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const longxinTail = runtime.decide(runtime.readState());
if (!longxinTail.nearest.includes("首日必须清仓") || longxinTail.ratio !== 100) {
  throw new Error(`longxin tail exit invalid: ${longxinTail.nearest} / ${longxinTail.ratio}`);
}

setInputs({
  clock: "11:05:00",
  currentPrice: 35.80,
  turnover: 62,
});
runtime.setSignalStateForTest({
  vwapBelowSince: Date.now() - 12 * 60 * 1000,
  vwapReboundFailedAt: Date.now() - 60 * 1000,
});
const longxinReboundFail = runtime.decide(runtime.readState());
if (!longxinReboundFail.nearest.includes("VWAP反抽失败") || longxinReboundFail.ratio !== 100) {
  throw new Error(`longxin VWAP rebound failure invalid: ${longxinReboundFail.nearest} / ${longxinReboundFail.ratio}`);
}

const singleLot = runtime.executableSell(100, 40);
if (singleLot.qty !== 0 || singleLot.pct !== 0) {
  throw new Error(`single lot soft sizing invalid: ${JSON.stringify(singleLot)}`);
}
const singleLotHard = runtime.executableSell(100, 100);
if (singleLotHard.qty !== 100 || singleLotHard.pct !== 100) {
  throw new Error(`single lot hard sizing invalid: ${JSON.stringify(singleLotHard)}`);
}
const fiveLots = runtime.executableSell(500, 40);
if (fiveLots.qty !== 200 || fiveLots.pct !== 40) {
  throw new Error(`five lot sizing invalid: ${JSON.stringify(fiveLots)}`);
}

setInputs({
  code: "920000",
  name: "问答测试",
  issuePrice: 10,
  floatCap: 6,
  position: 100,
  industryHeat: 1,
  peDiscount: 40,
  clock: "10:10:00",
  openPrice: 25,
  currentPrice: 22,
  highPrice: 28,
  lowPrice: 22,
  vwap: 24,
  turnover: 70,
  turnover30: 35,
  auctionRatio: 3,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const sellAnswer = runtime.answerQuestion("现在可以卖了吗");
if (!sellAnswer.includes("当前结论") || !sellAnswer.includes("100股")) {
  throw new Error(`sell question answer invalid: ${sellAnswer}`);
}
const quantityAnswer = runtime.answerQuestion("应该卖多少股");
if (!quantityAnswer.includes("100股")) {
  throw new Error(`quantity question answer invalid: ${quantityAnswer}`);
}

setInputs({
  code: "920900",
  name: "极高换手强承接",
  issuePrice: 10,
  floatCap: 5,
  position: 300,
  industryHeat: 1,
  peDiscount: "",
  clock: "10:05:00",
  openPrice: 40,
  currentPrice: 52,
  highPrice: 53,
  lowPrice: 40,
  vwap: 48,
  turnover: 70,
  turnover30: 55,
  auctionRatio: 6,
  unlock: 0,
  haltState: "auto",
  notes: "",
});
const extremeTurnoverStrong = runtime.decide(runtime.readState());
if (extremeTurnoverStrong.turnoverStructure.band.key !== "extreme"
  || extremeTurnoverStrong.turnoverStructure.key !== "strong"
  || extremeTurnoverStrong.ratio !== 0) {
  throw new Error(`extreme turnover strong must hold: ${JSON.stringify(extremeTurnoverStrong.turnoverStructure)} / ${extremeTurnoverStrong.ratio}`);
}

setInputs({
  clock: "10:05:00",
  openPrice: 40,
  currentPrice: 35,
  highPrice: 52,
  lowPrice: 35,
  vwap: 43,
  turnover: 72,
  turnover30: 45,
  auctionRatio: 4,
});
const activeDistribution = runtime.decide(runtime.readState());
if (activeDistribution.turnoverStructure.band.key !== "active"
  || activeDistribution.turnoverStructure.key !== "distribution"
  || activeDistribution.ratio <= 0) {
  throw new Error(`active turnover distribution must sell: ${JSON.stringify(activeDistribution.turnoverStructure)} / ${activeDistribution.ratio}`);
}

setInputs({
  clock: "10:05:00",
  openPrice: 40,
  currentPrice: 43,
  highPrice: 44,
  lowPrice: 40,
  vwap: 42,
  turnover: 24,
  turnover30: 22,
  auctionRatio: 1,
});
const lowTurnoverStable = runtime.decide(runtime.readState());
if (lowTurnoverStable.turnoverStructure.key !== "lowHold" || lowTurnoverStable.ratio !== 0) {
  throw new Error(`low turnover stable price must hold: ${JSON.stringify(lowTurnoverStable.turnoverStructure)} / ${lowTurnoverStable.ratio}`);
}

setInputs({
  clock: "10:05:00",
  openPrice: 40,
  currentPrice: 34,
  highPrice: 46,
  lowPrice: 34,
  vwap: 39,
  turnover: 25,
  turnover30: 24,
  auctionRatio: 1,
});
const lowTurnoverWeak = runtime.decide(runtime.readState());
if (lowTurnoverWeak.turnoverStructure.key !== "weakDemand" || lowTurnoverWeak.ratio <= 0) {
  throw new Error(`low turnover weak demand must sell: ${JSON.stringify(lowTurnoverWeak.turnoverStructure)} / ${lowTurnoverWeak.ratio}`);
}

const turnoverAnswer = runtime.answerQuestion("现在换手和热度怎么样");
if (!turnoverAnswer.includes("开盘30分钟累计换手") || !turnoverAnswer.includes("高换手不单独触发卖出")) {
  throw new Error(`turnover question answer invalid: ${turnoverAnswer}`);
}

setInputs({
  code: "920038",
  name: "森合高科",
  issuePrice: 29.06,
  targetPrice: 55,
  floatCap: 16.51,
  tradableSharesWan: 3416.6081,
  denominatorSource: "北交所上市公告书",
  denominatorVerified: 1,
  position: 100,
  singleLotMode: "tolerance",
  industryHeat: 1,
  peDiscount: 61.25,
  clock: "09:29:00",
  openPrice: 48.87,
  currentPrice: 48.87,
  highPrice: 48.87,
  lowPrice: 48.87,
  vwap: 48.87,
  turnover: 1.85,
  turnover30: "",
  auctionRatio: 1.85,
  auctionImbalance: "",
  auctionBookVerified: 0,
  unlock: 1,
  haltState: "auto",
  notes: "",
});
const lowAuctionDiscovery = runtime.decide(runtime.readState());
if (lowAuctionDiscovery.ratio !== 0
  || !lowAuctionDiscovery.reasons.some(item => item.text.includes("不单独触发卖出"))) {
  throw new Error(`low auction turnover must only lower confidence: ${lowAuctionDiscovery.ratio} / ${JSON.stringify(lowAuctionDiscovery.reasons)}`);
}

setInputs({
  clock: "09:35:54",
  currentPrice: 54.96,
  highPrice: 55.00,
  lowPrice: 48.87,
  vwap: 50.01,
  turnover: 16.80,
});
const targetExecution = runtime.decide(runtime.readState());
if (targetExecution.ratio !== 100
  || targetExecution.sellPrice !== 54.96
  || !targetExecution.targetSignals.atMarket
  || !targetExecution.nearest.includes("目标价 55.00 已进入成交区")) {
  throw new Error(`target price must execute explicitly: ${JSON.stringify(targetExecution)}`);
}
runtime.render();
if (element("actionTitle").textContent !== "立即卖出 100 股"
  || !element("actionBanner").className.includes("actionSell")) {
  throw new Error(`target execution banner must be explicit: ${element("actionTitle").textContent} / ${element("actionBanner").className}`);
}

setInputs({
  clock: "09:36:49",
  currentPrice: 52.40,
  highPrice: 55.55,
  lowPrice: 48.87,
  vwap: 50.42,
  turnover: 18.37,
  position: 100,
});
const targetFadeSingleLot = runtime.decide(runtime.readState());
if (targetFadeSingleLot.ratio !== 100
  || !targetFadeSingleLot.targetSignals.fadeConfirmed
  || !targetFadeSingleLot.nearest.includes("目标触达后量价背离")) {
  throw new Error(`single-lot target fade must sell all: ${JSON.stringify(targetFadeSingleLot)}`);
}

setInputs({position: 300});
const targetFadeMultiLot = runtime.decide(runtime.readState());
if (targetFadeMultiLot.ratio !== 50 || !targetFadeMultiLot.targetSignals.fadeConfirmed) {
  throw new Error(`multi-lot target fade should sell 50%: ${JSON.stringify(targetFadeMultiLot)}`);
}

setInputs({
  code: "920258",
  name: "上一只股票",
  issuePrice: 12,
  openPrice: 64.11,
  currentPrice: 66,
  highPrice: 75.12,
  lowPrice: 64,
  vwap: 69.07,
  turnover: 53,
  turnover30: 45,
  floatCap: 25,
  tradableSharesWan: 9999,
  denominatorSource: "旧口径",
  denominatorVerified: 1,
  targetPrice: "",
});
runtime.clearMarketState(true);
for (const id of ["name","issuePrice","targetPrice","openPrice","currentPrice","highPrice","lowPrice","vwap","turnover","turnover30","floatCap","tradableSharesWan","denominatorSource"]) {
  if (element(id).value !== "") throw new Error(`code switch must clear stale field ${id}`);
}
if (element("denominatorVerified").value !== "0") {
  throw new Error("code switch must reset denominator verification");
}

console.log("ALL_SCENARIOS_OK");
