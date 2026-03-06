const pptxgen = require('pptxgenjs');
const sharp = require('sharp');
const path = require('path');

const pptDir = '/root/.iflow-bot/workspace/mybot/ppt';
const imgDir = path.join(pptDir, 'images_v2');

// 高级渐变背景生成
async function createGradientBg(filename, colors, angle = 135) {
  const [c1, c2, c3] = colors;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs>
      <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:${c1}"/>
        <stop offset="50%" style="stop-color:${c2}"/>
        <stop offset="100%" style="stop-color:${c3}"/>
      </linearGradient>
    </defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
  </svg>`;
  await sharp(Buffer.from(svg)).png().toFile(path.join(pptDir, filename));
  return filename;
}

// 创建闪电特效背景
async function createLightningBg(filename) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs>
      <radialGradient id="bg" cx="50%" cy="50%" r="70%">
        <stop offset="0%" style="stop-color:#2a1b3d"/>
        <stop offset="100%" style="stop-color:#0d0d1a"/>
      </radialGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    <rect width="100%" height="100%" fill="url(#bg)"/>
    <g filter="url(#glow)" opacity="0.8">
      <polyline points="100,200 150,350 120,360 200,500 160,510 280,700" stroke="#a855f7" stroke-width="3" fill="none"/>
      <polyline points="1800,100 1750,250 1780,260 1700,400 1740,410 1620,600" stroke="#c084fc" stroke-width="2" fill="none"/>
      <polyline points="500,800 550,650 520,640 600,500 560,490 680,300" stroke="#e879f9" stroke-width="2" fill="none"/>
      <polyline points="1400,900 1350,750 1380,740 1300,600 1340,590 1220,400" stroke="#a855f7" stroke-width="3" fill="none"/>
    </g>
  </svg>`;
  await sharp(Buffer.from(svg)).png().toFile(path.join(pptDir, filename));
  return filename;
}

// 创建星空背景
async function createStarfieldBg(filename) {
  let stars = '';
  for(let i = 0; i < 200; i++) {
    const x = Math.random() * 1920;
    const y = Math.random() * 1080;
    const r = Math.random() * 2 + 0.5;
    const opacity = Math.random() * 0.8 + 0.2;
    stars += `<circle cx="${x}" cy="${y}" r="${r}" fill="#ffffff" opacity="${opacity}"/>`;
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs>
      <linearGradient id="sky" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" style="stop-color:#0a0a1a"/>
        <stop offset="50%" style="stop-color:#1a1a3a"/>
        <stop offset="100%" style="stop-color:#2a1b4a"/>
      </linearGradient>
    </defs>
    <rect width="100%" height="100%" fill="url(#sky)"/>
    ${stars}
  </svg>`;
  await sharp(Buffer.from(svg)).png().toFile(path.join(pptDir, filename));
  return filename;
}

async function createPresentation() {
  console.log('开始创建高端PPT...');
  
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'iFlow AI';
  pptx.title = '刻晴 - 霆霓快雨';
  pptx.subject = '原神角色介绍';
  
  // 创建背景
  const bg1 = await createGradientBg('bg_purple.png', ['#1a0a2e', '#2d1b4e', '#1a0a2e']);
  const bg2 = await createGradientBg('bg_dark.png', ['#0d0d1a', '#1a1a2e', '#0d0d1a']);
  const bg3 = await createLightningBg('bg_lightning.png');
  const bg4 = await createStarfieldBg('bg_stars.png');
  
  console.log('背景创建完成');
  
  // ==================== 第1页：炫酷开场 ====================
  const slide1 = pptx.addSlide();
  slide1.background = { path: path.join(pptDir, bg3) };
  
  // 标题动画 - 从左飞入
  slide1.addText('刻晴', {
    x: -10, y: 1.8, w: 10, h: 2,
    fontSize: 120, fontFace: 'Arial', bold: true,
    color: 'ffffff',
    shadow: { type: 'outer', blur: 20, offset: 0, angle: 0, color: 'a855f7', opacity: 0.8 },
    align: 'center'
  });
  
  // 副标题
  slide1.addText('霆霓快雨 · 玉衡星', {
    x: 0, y: 3.8, w: 10, h: 0.8,
    fontSize: 36, fontFace: 'Arial',
    color: 'c084fc', align: 'center'
  });
  
  // 英文名
  slide1.addText('KEQING', {
    x: 0, y: 4.6, w: 10, h: 0.6,
    fontSize: 24, fontFace: 'Arial', bold: true,
    color: 'e879f9', align: 'center', charSpacing: 8
  });
  
  // 底部装饰线
  slide1.addShape(pptx.shapes.RECTANGLE, {
    x: 3.5, y: 5.2, w: 3, h: 0.03,
    fill: { color: 'a855f7' },
    shadow: { type: 'outer', blur: 10, offset: 0, angle: 0, color: 'a855f7', opacity: 0.6 }
  });
  
  // Genshin Impact 标识
  slide1.addText('GENSHIN IMPACT', {
    x: 0, y: 5.3, w: 10, h: 0.4,
    fontSize: 12, fontFace: 'Arial',
    color: '666666', align: 'center'
  });

  // ==================== 第2页：角色立绘展示 ====================
  const slide2 = pptx.addSlide();
  slide2.background = { path: path.join(pptDir, bg4) };
  
  // 左侧大图
  slide2.addImage({
    path: path.join(imgDir, 'keqing_birthday1.png'),
    x: -0.5, y: -0.3, w: 5.5, h: 6.3,
    sizing: { type: 'contain' }
  });
  
  // 右侧信息面板
  slide2.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 5.2, y: 0.5, w: 4.5, h: 4.8,
    fill: { color: '1a0a2e', transparency: 40 },
    line: { color: 'a855f7', width: 1 },
    rectRadius: 0.15
  });
  
  slide2.addText('角色简介', {
    x: 5.5, y: 0.7, w: 4, h: 0.6,
    fontSize: 28, bold: true, color: 'e879f9'
  });
  
  const infoData = [
    ['称号', '霆霓快雨'],
    ['所属', '璃月七星·玉衡星'],
    ['神之眼', '雷元素'],
    ['武器', '单手剑'],
    ['稀有度', '★★★★★'],
    ['生日', '11月20日'],
    ['CV', '谢莹(中) / 喜多村英梨(日)']
  ];
  
  infoData.forEach((item, i) => {
    slide2.addText(item[0], { x: 5.5, y: 1.4 + i * 0.5, w: 1.2, h: 0.4, fontSize: 11, color: 'a855f7' });
    slide2.addText(item[1], { x: 6.8, y: 1.4 + i * 0.5, w: 2.5, h: 0.4, fontSize: 12, color: 'ffffff' });
  });

  // ==================== 第3页：照片墙 ====================
  const slide3 = pptx.addSlide();
  slide3.background = { path: path.join(pptDir, bg1) };
  
  slide3.addText('刻晴 · 立绘画廊', {
    x: 0.5, y: 0.3, w: 9, h: 0.7,
    fontSize: 32, bold: true, color: 'e879f9', align: 'center'
  });
  
  // 3x3 照片墙布局
  const photos = [
    { path: 'keqing_render1.png', x: 0.3, y: 1, w: 3, h: 2.1 },
    { path: 'keqing_render2.png', x: 3.5, y: 1, w: 3, h: 2.1 },
    { path: 'keqing_render3.png', x: 6.7, y: 1, w: 3, h: 2.1 },
    { path: 'keqing_render4.png', x: 0.3, y: 3.3, w: 3, h: 2.1 },
    { path: 'keqing_birthday2.png', x: 3.5, y: 3.3, w: 3, h: 2.1 },
    { path: 'keqing_render5.png', x: 6.7, y: 3.3, w: 3, h: 2.1 }
  ];
  
  photos.forEach(p => {
    slide3.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: p.x - 0.05, y: p.y - 0.05, w: p.w + 0.1, h: p.h + 0.1,
      fill: { color: '2a1b4e' },
      line: { color: 'a855f7', width: 2 },
      rectRadius: 0.08
    });
    slide3.addImage({
      path: path.join(imgDir, p.path),
      x: p.x, y: p.y, w: p.w, h: p.h,
      sizing: { type: 'contain' }
    });
  });

  // ==================== 第4页：背景故事 ====================
  const slide4 = pptx.addSlide();
  slide4.background = { path: path.join(pptDir, bg2) };
  
  // 左侧图片
  slide4.addImage({
    path: path.join(imgDir, 'keqing_render6.png'),
    x: 0, y: 0, w: 4.5, h: 5.63,
    sizing: { type: 'contain' }
  });
  
  // 右侧文字
  slide4.addText('背景故事', {
    x: 4.8, y: 0.3, w: 5, h: 0.7,
    fontSize: 32, bold: true, color: 'e879f9'
  });
  
  const storyText = `璃月七星之一，玉衡星。

她对「帝君一言而决的璃月」颇有微词——但实际上，神挺欣赏她这样的人。

身为璃月七星，刻晴是个不折不扣的行动派。如果一件事在她看来是有价值、有必要的，那她一定会亲力亲为。

她曾亲自踏遍璃月全境，将地势地貌牢记于心，以便日后能够最大限度地利用每一寸土地。

「帝君已经守护了璃月千年，但下一个千年，十个千年，一百个千年，也会是如此吗？」`;
  
  slide4.addText(storyText, {
    x: 4.8, y: 1.1, w: 4.8, h: 4,
    fontSize: 13, color: 'cccccc', valign: 'top', lineSpacing: 22
  });

  // ==================== 第5页：元素战技 ====================
  const slide5 = pptx.addSlide();
  slide5.background = { path: path.join(pptDir, bg3) };
  
  slide5.addText('元素战技', {
    x: 0.5, y: 0.3, w: 9, h: 0.7,
    fontSize: 32, bold: true, color: 'e879f9', align: 'center'
  });
  
  // 技能卡片
  const skillCards = [
    { 
      name: '星斗归位', 
      desc: '迅速投出雷楔，以疾雷之势歼敌。雷楔命中时造成雷元素伤害。再次施放可瞬移到标记处斩击。',
      img: 'keqing_render7.png'
    },
    { 
      name: '重击·雷暴连斩', 
      desc: '在雷楔存在期间施展重击，在标记处引发雷暴连斩，造成数次雷元素范围伤害。',
      img: 'keqing_render8.png'
    }
  ];
  
  skillCards.forEach((skill, i) => {
    const x = 0.5 + i * 4.8;
    slide5.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: x, y: 1, w: 4.5, h: 4.3,
      fill: { color: '1a0a2e', transparency: 30 },
      line: { color: 'a855f7', width: 2 },
      rectRadius: 0.12
    });
    slide5.addImage({
      path: path.join(imgDir, skill.img),
      x: x + 0.3, y: 1.2, w: 3.9, h: 2.2,
      sizing: { type: 'contain' }
    });
    slide5.addText(skill.name, {
      x: x + 0.2, y: 3.5, w: 4.1, h: 0.5,
      fontSize: 20, bold: true, color: 'e879f9', align: 'center'
    });
    slide5.addText(skill.desc, {
      x: x + 0.2, y: 4, w: 4.1, h: 1.2,
      fontSize: 11, color: 'cccccc', align: 'center', valign: 'top'
    });
  });

  // ==================== 第6页：元素爆发 ====================
  const slide6 = pptx.addSlide();
  slide6.background = { path: path.join(pptDir, bg1) };
  
  // 大图背景
  slide6.addImage({
    path: path.join(imgDir, 'keqing_birthday1.png'),
    x: 5, y: -0.5, w: 5.5, h: 6.5,
    sizing: { type: 'contain' }
  });
  
  // 左侧内容
  slide6.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 0.3, y: 0.5, w: 4.8, h: 4.8,
    fill: { color: '0d0d1a', transparency: 20 },
    line: { color: 'a855f7', width: 2 },
    rectRadius: 0.15
  });
  
  slide6.addText('元素爆发', {
    x: 0.5, y: 0.7, w: 4.5, h: 0.6,
    fontSize: 28, bold: true, color: 'e879f9'
  });
  
  slide6.addText('天街巡游', {
    x: 0.5, y: 1.4, w: 4.5, h: 0.5,
    fontSize: 22, bold: true, color: 'ffffff'
  });
  
  slide6.addText(`以极快的速度斩击周围的敌人，造成大量雷元素范围伤害。

技能包含多段连斩伤害，最后一击会造成巨额伤害，是刻晴输出的核心技能之一。

• 技能伤害: 88.0% ~ 198%
• 连斩伤害: 24.0%×8 ~ 54.0%×8
• 最后一击: 189% ~ 425%
• 冷却时间: 12秒
• 元素能量: 40`, {
    x: 0.5, y: 2, w: 4.3, h: 3,
    fontSize: 12, color: 'cccccc', valign: 'top', lineSpacing: 18
  });

  // ==================== 第7页：命之座 ====================
  const slide7 = pptx.addSlide();
  slide7.background = { path: path.join(pptDir, bg4) };
  
  slide7.addText('命之座 · 金紫定垂座', {
    x: 0.5, y: 0.2, w: 9, h: 0.6,
    fontSize: 28, bold: true, color: 'e879f9', align: 'center'
  });
  
  const constellations = [
    { name: '一命·雷厉', desc: '瞬移时造成50%攻击力雷元素范围伤害', tier: 'C1' },
    { name: '二命·苛捐', desc: '命中雷元素敌人50%几率产生元素微粒', tier: 'C2' },
    { name: '四命·调律', desc: '触发雷元素反应后攻击力+25%，持续10秒', tier: 'C4' },
    { name: '六命·廉贞', desc: '施放技能获得6%雷伤加成，各效果独立叠加', tier: 'C6' }
  ];
  
  constellations.forEach((c, i) => {
    const x = 0.3 + (i % 2) * 4.9;
    const y = 0.9 + Math.floor(i / 2) * 2.3;
    
    slide7.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: x, y: y, w: 4.7, h: 2.1,
      fill: { color: '1a0a2e', transparency: 30 },
      line: { color: 'a855f7', width: 1.5 },
      rectRadius: 0.1
    });
    
    // 命座标识
    slide7.addShape(pptx.shapes.OVAL, {
      x: x + 0.15, y: y + 0.15, w: 0.6, h: 0.6,
      fill: { color: 'a855f7' }
    });
    slide7.addText(c.tier, {
      x: x + 0.15, y: y + 0.2, w: 0.6, h: 0.5,
      fontSize: 12, bold: true, color: 'ffffff', align: 'center'
    });
    
    slide7.addText(c.name, {
      x: x + 0.85, y: y + 0.2, w: 3.5, h: 0.5,
      fontSize: 18, bold: true, color: 'e879f9'
    });
    slide7.addText(c.desc, {
      x: x + 0.85, y: y + 0.8, w: 3.5, h: 1,
      fontSize: 11, color: 'cccccc', valign: 'top'
    });
  });

  // ==================== 第8页：装备推荐 ====================
  const slide8 = pptx.addSlide();
  slide8.background = { path: path.join(pptDir, bg2) };
  
  slide8.addText('装备推荐', {
    x: 0.5, y: 0.2, w: 9, h: 0.6,
    fontSize: 28, bold: true, color: 'e879f9', align: 'center'
  });
  
  const equipCards = [
    { title: '武器', items: ['五星: 雾切之回光', '五星: 磐岩结绿', '四星: 黑剑', '四星: 笼钓瓶一心'] },
    { title: '圣遗物', items: ['如雷的盛怒 4件', '饰金之梦 4件', '角斗士2+如雷2', '平雷4件'] },
    { title: '主词条', items: ['时之沙: 攻击/精通', '空之杯: 雷伤加成', '理之冠: 暴击/暴伤', '副词条: 双暴>攻击>精通'] }
  ];
  
  equipCards.forEach((card, i) => {
    const x = 0.3 + i * 3.2;
    slide8.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: x, y: 0.9, w: 3, h: 4.5,
      fill: { color: '1a0a2e', transparency: 30 },
      line: { color: 'a855f7', width: 1.5 },
      rectRadius: 0.12
    });
    slide8.addText(card.title, {
      x: x + 0.15, y: 1, w: 2.7, h: 0.5,
      fontSize: 18, bold: true, color: 'e879f9', align: 'center'
    });
    slide8.addShape(pptx.shapes.RECTANGLE, {
      x: x + 0.3, y: 1.5, w: 2.4, h: 0.02,
      fill: { color: 'a855f7' }
    });
    card.items.forEach((item, j) => {
      slide8.addText(item, {
        x: x + 0.15, y: 1.7 + j * 0.7, w: 2.7, h: 0.6,
        fontSize: 11, color: 'cccccc', align: 'center'
      });
    });
  });

  // ==================== 第9页：配队推荐 ====================
  const slide9 = pptx.addSlide();
  slide9.background = { path: path.join(pptDir, bg1) };
  
  slide9.addText('配队推荐', {
    x: 0.5, y: 0.2, w: 9, h: 0.6,
    fontSize: 28, bold: true, color: 'e879f9', align: 'center'
  });
  
  const teams = [
    { name: '激化队', chars: '刻晴 + 纳西妲 + 菲谢尔 + 钟离', desc: '草雷激化反应大幅提升雷伤输出', rating: '★★★★★' },
    { name: '超导物理队', chars: '刻晴 + 菲谢尔 + 罗莎莉亚 + 迪奥娜', desc: '超导降低物抗，配合物理圣遗物', rating: '★★★★' },
    { name: '纯雷队', chars: '刻晴 + 菲谢尔 + 北斗 + 班尼特', desc: '双雷共鸣，班尼特攻击加成', rating: '★★★★' }
  ];
  
  teams.forEach((team, i) => {
    const x = 0.3 + i * 3.2;
    slide9.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: x, y: 0.9, w: 3, h: 4.5,
      fill: { color: '1a0a2e', transparency: 30 },
      line: { color: 'a855f7', width: 1.5 },
      rectRadius: 0.12
    });
    slide9.addText(team.name, {
      x: x + 0.1, y: 1, w: 2.8, h: 0.5,
      fontSize: 18, bold: true, color: 'e879f9', align: 'center'
    });
    slide9.addText(team.rating, {
      x: x + 0.1, y: 1.45, w: 2.8, h: 0.35,
      fontSize: 10, color: 'fbbf24', align: 'center'
    });
    slide9.addText(team.chars, {
      x: x + 0.1, y: 1.9, w: 2.8, h: 0.7,
      fontSize: 10, color: 'ffffff', align: 'center', bold: true
    });
    slide9.addText(team.desc, {
      x: x + 0.1, y: 2.7, w: 2.8, h: 1.5,
      fontSize: 10, color: 'aaaaaa', align: 'center', valign: 'top'
    });
  });

  // ==================== 第10页：角色名句 ====================
  const slide10 = pptx.addSlide();
  slide10.background = { path: path.join(pptDir, bg3) };
  
  // 名句背景框
  slide10.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 1, y: 1.5, w: 8, h: 2.5,
    fill: { color: '1a0a2e', transparency: 50 },
    line: { color: 'a855f7', width: 2 },
    rectRadius: 0.15
  });
  
  slide10.addText(`「人像是蛾子，总奔着名叫神仙的火光而去。`, {
    x: 1.2, y: 1.7, w: 7.6, h: 0.8,
    fontSize: 22, italic: true, color: 'e879f9', align: 'center'
  });
  slide10.addText(`但是我这光是自己点的。」`, {
    x: 1.2, y: 2.5, w: 7.6, h: 0.6,
    fontSize: 22, italic: true, color: 'e879f9', align: 'center'
  });
  slide10.addText('—— 刻晴', {
    x: 1.2, y: 3.3, w: 7.6, h: 0.5,
    fontSize: 14, color: 'aaaaaa', align: 'right'
  });

  // ==================== 第11页：更多图片展示 ====================
  const slide11 = pptx.addSlide();
  slide11.background = { path: path.join(pptDir, bg4) };
  
  slide11.addText('刻晴 · 精选图集', {
    x: 0.5, y: 0.2, w: 9, h: 0.5,
    fontSize: 26, bold: true, color: 'e879f9', align: 'center'
  });
  
  // 不规则照片墙
  const gallery = [
    { path: 'keqing_render2.png', x: 0.2, y: 0.8, w: 3.2, h: 2.4, rot: -2 },
    { path: 'keqing_render3.png', x: 3.5, y: 0.7, w: 3, h: 2.3, rot: 1 },
    { path: 'keqing_render4.png', x: 6.6, y: 0.8, w: 3.2, h: 2.4, rot: 2 },
    { path: 'keqing_render5.png', x: 0.3, y: 3.3, w: 3, h: 2.2, rot: 1 },
    { path: 'keqing_render6.png', x: 3.4, y: 3.2, w: 3.2, h: 2.3, rot: -1 },
    { path: 'keqing_render7.png', x: 6.7, y: 3.3, w: 3.1, h: 2.2, rot: -2 }
  ];
  
  gallery.forEach(g => {
    slide11.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: g.x - 0.03, y: g.y - 0.03, w: g.w + 0.06, h: g.h + 0.06,
      fill: { color: '2a1b4e' },
      line: { color: 'a855f7', width: 1.5 },
      rectRadius: 0.06,
      rotate: g.rot
    });
    slide11.addImage({
      path: path.join(imgDir, g.path),
      x: g.x, y: g.y, w: g.w, h: g.h,
      sizing: { type: 'contain' },
      rotate: g.rot
    });
  });

  // ==================== 第12页：感谢页 ====================
  const slide12 = pptx.addSlide();
  slide12.background = { path: path.join(pptDir, bg3) };
  
  // 中央图片
  slide12.addImage({
    path: path.join(imgDir, 'keqing_birthday1.png'),
    x: 2.5, y: 0, w: 5, h: 5.63,
    sizing: { type: 'contain' }
  });
  
  // 遮罩层
  slide12.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 5.63,
    fill: { color: '000000', transparency: 60 }
  });
  
  slide12.addText('感谢观看', {
    x: 0, y: 1.5, w: 10, h: 1,
    fontSize: 48, bold: true, color: 'ffffff', align: 'center',
    shadow: { type: 'outer', blur: 15, offset: 0, angle: 0, color: 'a855f7', opacity: 0.6 }
  });
  
  slide12.addText('刻晴 · 霆霓快雨', {
    x: 0, y: 2.5, w: 10, h: 0.6,
    fontSize: 24, color: 'e879f9', align: 'center'
  });
  
  slide12.addText('GENSHIN IMPACT © miHoYo', {
    x: 0, y: 4.8, w: 10, h: 0.4,
    fontSize: 12, color: '666666', align: 'center'
  });

  // 添加页面切换动画
  const transitions = [
    { type: 'fade' }, { type: 'push', direction: 'right' },
    { type: 'wipe', direction: 'right' }, { type: 'fade' },
    { type: 'push', direction: 'up' }, { type: 'fade' },
    { type: 'wipe', direction: 'left' }, { type: 'fade' },
    { type: 'push', direction: 'down' }, { type: 'fade' },
    { type: 'wipe', direction: 'right' }, { type: 'fade' }
  ];
  
  pptx.slides.forEach((slide, i) => {
    if (transitions[i]) {
      slide.transition = { ...transitions[i], speed: 'fast' };
    }
  });

  // 保存文件
  const outputPath = path.join(pptDir, '刻晴角色介绍_高级版.pptx');
  await pptx.writeFile({ fileName: outputPath });
  console.log(`PPT创建成功: ${outputPath}`);
}

createPresentation().catch(console.error);
