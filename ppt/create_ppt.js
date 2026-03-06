const pptxgen = require('pptxgenjs');
const path = require('path');
const html2pptx = require('/root/.iflow-bot/workspace/mybot/.agents/skills/pptx/scripts/html2pptx');
const sharp = require('sharp');

async function createGradientBackground(filename, color1, color2) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs>
      <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:${color1}"/>
        <stop offset="100%" style="stop-color:${color2}"/>
      </linearGradient>
    </defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
  </svg>`;
  await sharp(Buffer.from(svg)).png().toFile(filename);
  return filename;
}

async function createPresentation() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'iFlow AI';
  pptx.title = '刻晴 - 霆霓快雨';
  pptx.subject = '原神角色介绍';
  
  const pptDir = '/root/.iflow-bot/workspace/mybot/ppt';
  
  // Create gradient backgrounds for slides that need them
  const gradientBg1 = await createGradientBackground(path.join(pptDir, 'gradient1.png'), '#1a1a2e', '#0f3460');
  
  // Slide 1: Title
  const slide1 = pptx.addSlide();
  slide1.background = { path: gradientBg1 };
  slide1.addText('刻晴 - 霆霓快雨', { 
    x: 0.5, y: 1.5, w: 9, h: 1.2, 
    fontSize: 48, bold: true, color: 'e94560', align: 'center',
    shadow: { type: 'outer', blur: 4, offset: 2, angle: 45, color: '000000', opacity: 0.5 }
  });
  slide1.addText('Genshin Impact - Keqing', { 
    x: 0.5, y: 2.8, w: 9, h: 0.6, 
    fontSize: 24, color: 'ffffff', align: 'center' 
  });
  slide1.addText('璃月七星 · 玉衡星', { 
    x: 0.5, y: 3.6, w: 9, h: 0.5, 
    fontSize: 16, color: 'a2d2ff', align: 'center' 
  });
  
  // Slide 2: Character Profile
  const slide2 = pptx.addSlide();
  slide2.background = { color: '1a1a2e' };
  slide2.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 0.3, h: 5.63, fill: { color: 'e94560' } });
  slide2.addText('角色简介', { x: 0.5, y: 0.3, w: 4, h: 0.7, fontSize: 32, bold: true, color: 'e94560' });
  
  const infoItems = [
    ['称号', '霆霓快雨 · 玉衡星'],
    ['所属地区', '璃月'],
    ['神之眼', '雷元素'],
    ['武器类型', '单手剑'],
    ['稀有度', '5星'],
    ['生日', '11月20日'],
    ['中文CV', '谢莹']
  ];
  
  let yPos = 1.2;
  infoItems.forEach(item => {
    slide2.addText(item[0], { x: 0.5, y: yPos, w: 2, h: 0.35, fontSize: 12, color: 'a2d2ff' });
    slide2.addText(item[1], { x: 0.5, y: yPos + 0.3, w: 4, h: 0.35, fontSize: 14, color: 'ffffff' });
    yPos += 0.6;
  });
  
  slide2.addImage({ path: path.join(pptDir, 'images/keqing1.png'), x: 5.5, y: 0.3, w: 4, h: 5 });
  
  // Slide 3: Background Story
  const slide3 = pptx.addSlide();
  slide3.background = { color: '16213e' };
  slide3.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: 'e94560' } });
  slide3.addText('背景故事', { x: 0.5, y: 0.2, w: 9, h: 0.6, fontSize: 28, bold: true, color: 'ffffff' });
  
  const storyContent = [
    { title: '璃月七星', text: '刻晴是璃月七星之一，担任玉衡星一职。她对「帝君一言而决的璃月」颇有微词，但实际上，神明非常欣赏她这样的人。' },
    { title: '理念与追求', text: '她坚信与人类命运相关的事，应当由人类去做，而且人类一定可以做得更好。这种激进的观念让她成为璃月变革的先驱者。' },
    { title: '工作态度', text: '身为璃月七星，刻晴是个不折不扣的行动派。如果一件事在她看来有价值、有必要，她一定会亲力亲为。' },
    { title: '经典语录', text: '「帝君已经守护了璃月千年，但下一个千年，十个千年，一百个千年，也会是如此吗？」' }
  ];
  
  yPos = 1.2;
  storyContent.forEach(item => {
    slide3.addText(item.title, { x: 0.5, y: yPos, w: 4, h: 0.4, fontSize: 16, bold: true, color: 'a2d2ff' });
    slide3.addText(item.text, { x: 0.5, y: yPos + 0.4, w: 9, h: 0.6, fontSize: 12, color: 'ffffff' });
    yPos += 1;
  });
  
  // Slide 4: Skills - Elemental Skill
  const slide4 = pptx.addSlide();
  slide4.background = { color: '1a1a2e' };
  slide4.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: 'e94560' } });
  slide4.addText('技能介绍 - 元素战技', { x: 0.5, y: 0.2, w: 9, h: 0.6, fontSize: 28, bold: true, color: 'ffffff' });
  
  const skills = [
    { name: '星斗归位', type: '元素战技', desc: '迅速投出雷楔，以疾雷之势歼敌。雷楔命中时会对小范围内的敌人造成雷元素伤害。再次施放可瞬移到标记处进行斩击。' },
    { name: '重击·雷暴连斩', type: '派生技能', desc: '在雷楔存在期间施展重击，会在标记处引发雷暴连斩，造成数次雷元素范围伤害。' },
    { name: '抵天雷罚', type: '突破天赋', desc: '雷楔存在期间再次施放星斗归位后的5秒内，刻晴获得雷元素附魔，普通攻击转化为雷元素伤害。' }
  ];
  
  skills.forEach((skill, idx) => {
    const x = 0.5 + idx * 3.1;
    slide4.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: x, y: 1.1, w: 3, h: 3.8, fill: { color: '16213e' }, line: { color: 'e94560', width: 2 }, rectRadius: 0.1 });
    slide4.addShape(pptx.shapes.RECTANGLE, { x: x, y: 1.1, w: 0.08, h: 3.8, fill: { color: 'e94560' } });
    slide4.addText(skill.name, { x: x + 0.15, y: 1.2, w: 2.7, h: 0.5, fontSize: 14, bold: true, color: 'e94560' });
    slide4.addText(skill.type, { x: x + 0.15, y: 1.65, w: 2.7, h: 0.3, fontSize: 10, color: 'a2d2ff' });
    slide4.addText(skill.desc, { x: x + 0.15, y: 2, w: 2.7, h: 2.5, fontSize: 10, color: 'ffffff', valign: 'top' });
  });
  
  // Slide 5: Elemental Burst
  const slide5 = pptx.addSlide();
  slide5.background = { color: '16213e' };
  slide5.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: 'e94560' } });
  slide5.addText('技能介绍 - 元素爆发', { x: 0.5, y: 0.2, w: 9, h: 0.6, fontSize: 28, bold: true, color: 'ffffff' });
  
  slide5.addText('天街巡游', { x: 0.5, y: 1.2, w: 5, h: 0.6, fontSize: 20, bold: true, color: 'e94560' });
  slide5.addText('刻晴的元素爆发技能，以极快的速度斩击周围的敌人，造成大量雷元素范围伤害。技能包含多段连斩伤害，最后一击会造成巨额伤害，是刻晴输出的核心技能之一。', 
    { x: 0.5, y: 1.9, w: 5, h: 1.2, fontSize: 12, color: 'ffffff' });
  slide5.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.2, w: 5, h: 1, fill: { color: '0f3460' }, line: { color: 'a2d2ff', width: 1 }, rectRadius: 0.05 });
  slide5.addText('突破天赋「玉衡之贵」：施放天街巡游时，刻晴的暴击率提升15%，元素充能效率提升15%，持续8秒。', 
    { x: 0.6, y: 3.3, w: 4.8, h: 0.8, fontSize: 11, color: 'a2d2ff' });
  slide5.addImage({ path: path.join(pptDir, 'images/keqing2.png'), x: 5.8, y: 0.8, w: 3.8, h: 4.5 });
  
  // Slide 6: Constellations
  const slide6 = pptx.addSlide();
  slide6.background = { color: '1a1a2e' };
  slide6.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: 'e94560' } });
  slide6.addText('命之座 - 金紫定垂座', { x: 0.5, y: 0.2, w: 9, h: 0.6, fontSize: 28, bold: true, color: 'ffffff' });
  
  const constellations = [
    { name: '一命 · 雷厉', desc: '雷楔存在期间再次施放星斗归位时，在刻晴消失与出现的位置造成50%攻击力的雷元素范围伤害。' },
    { name: '二命 · 苛捐', desc: '刻晴普通攻击与重击命中受到雷元素影响的敌人时，有50%几率产生一个元素微粒。' },
    { name: '四命 · 调律', desc: '刻晴触发雷元素相关反应后的10秒内，攻击力提升25%。' },
    { name: '六命 · 廉贞', desc: '进行普通攻击、重击、施放元素战技或元素爆发时，获得6%雷元素伤害加成，持续8秒，各效果独立存在。' }
  ];
  
  constellations.forEach((c, idx) => {
    const x = 0.5 + (idx % 2) * 4.7;
    const y = 1.1 + Math.floor(idx / 2) * 2.1;
    slide6.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: x, y: y, w: 4.5, h: 2, fill: { color: '16213e' }, rectRadius: 0.1 });
    slide6.addShape(pptx.shapes.RECTANGLE, { x: x, y: y, w: 4.5, h: 0.06, fill: { color: 'e94560' } });
    slide6.addText(c.name, { x: x + 0.15, y: y + 0.15, w: 4.2, h: 0.4, fontSize: 13, bold: true, color: 'e94560' });
    slide6.addText(c.desc, { x: x + 0.15, y: y + 0.6, w: 4.2, h: 1.3, fontSize: 10, color: 'ffffff', valign: 'top' });
  });
  
  // Slide 7: Combat Role
  const slide7 = pptx.addSlide();
  slide7.background = { color: '16213e' };
  slide7.addImage({ path: path.join(pptDir, 'images/keqing3.png'), x: 0.3, y: 0.3, w: 3.5, h: 5 });
  slide7.addText('战斗定位', { x: 4, y: 0.5, w: 5.5, h: 0.7, fontSize: 28, bold: true, color: 'e94560' });
  
  const roles = [
    { title: '主C输出', text: '刻晴作为雷元素单手剑角色，凭借高频的攻击和灵活的位移能力，非常适合担任队伍的主C输出位置。' },
    { title: '激化反应', text: '配合草元素角色可以触发激化反应，大幅提升雷元素伤害，是目前最主流的配队方向。' },
    { title: '探索能力', text: '星斗归位可以跨越地形障碍，是探索地图的利器。突破天赋「总务土地」还能缩短璃月探索派遣时间。' }
  ];
  
  yPos = 1.3;
  roles.forEach(role => {
    slide7.addText(role.title, { x: 4, y: yPos, w: 5.5, h: 0.4, fontSize: 16, bold: true, color: 'a2d2ff' });
    slide7.addText(role.text, { x: 4, y: yPos + 0.4, w: 5.5, h: 0.8, fontSize: 12, color: 'ffffff' });
    yPos += 1.3;
  });
  
  // Slide 8: Equipment
  const slide8 = pptx.addSlide();
  slide8.background = { color: '1a1a2e' };
  slide8.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: 'e94560' } });
  slide8.addText('装备推荐', { x: 0.5, y: 0.2, w: 9, h: 0.6, fontSize: 28, bold: true, color: 'ffffff' });
  
  const equipment = [
    { title: '武器推荐', items: ['五星：雾切之回光 · 磐岩结绿', '四星：黑剑 · 笼钓瓶一心', '三星：黎明神剑'] },
    { title: '圣遗物套装', items: ['主流：如雷的盛怒 4件', '替代：饰金之梦 4件', '其他：平雷4/角斗士2+如雷2'] },
    { title: '属性优先级', items: ['时之沙：攻击/精通', '空之杯：雷伤加成', '理之冠：暴击/暴伤'] }
  ];
  
  equipment.forEach((eq, idx) => {
    const x = 0.5 + idx * 3.2;
    slide8.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: x, y: 1.1, w: 3, h: 3.8, fill: { color: '16213e' }, rectRadius: 0.1 });
    slide8.addText(eq.title, { x: x + 0.15, y: 1.2, w: 2.7, h: 0.5, fontSize: 16, bold: true, color: 'e94560' });
    slide8.addShape(pptx.shapes.RECTANGLE, { x: x + 0.15, y: 1.65, w: 2.7, h: 0.02, fill: { color: '0f3460' } });
    eq.items.forEach((item, i) => {
      slide8.addText(item, { x: x + 0.15, y: 1.8 + i * 0.7, w: 2.7, h: 0.6, fontSize: 11, color: 'ffffff' });
    });
  });
  
  // Slide 9: Team Recommendations
  const slide9 = pptx.addSlide();
  slide9.background = { color: '16213e' };
  slide9.addShape(pptx.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: 'e94560' } });
  slide9.addText('配队推荐', { x: 0.5, y: 0.2, w: 9, h: 0.6, fontSize: 28, bold: true, color: 'ffffff' });
  
  const teams = [
    { name: '激化队', comp: '刻晴 + 纳西妲 + 菲谢尔 + 钟离', role: '主C + 草副C + 雷副C + 盾辅', desc: '利用草雷激化反应大幅提升输出，是目前最强的刻晴配队之一。' },
    { name: '超导物理队', comp: '刻晴 + 菲谢尔 + 罗莎莉亚 + 迪奥娜', role: '主C + 雷副C + 冰副C + 治疗', desc: '超导降低物抗，配合物理伤害加成圣遗物打出高额物理伤害。' },
    { name: '纯雷队', comp: '刻晴 + 菲谢尔 + 北斗 + 班尼特', role: '主C + 雷副C + 雷副C + 攻辅', desc: '双雷共鸣提升充能效率，班尼特提供攻击加成和治疗。' }
  ];
  
  teams.forEach((team, idx) => {
    const x = 0.5 + idx * 3.2;
    slide9.addShape(pptx.shapes.ROUNDED_RECTANGLE, { x: x, y: 1.1, w: 3, h: 3.8, fill: { color: '1a1a2e' }, rectRadius: 0.1 });
    slide9.addShape(pptx.shapes.RECTANGLE, { x: x, y: 1.1, w: 3, h: 0.08, fill: { color: 'a2d2ff' } });
    slide9.addText(team.name, { x: x + 0.15, y: 1.25, w: 2.7, h: 0.4, fontSize: 16, bold: true, color: 'a2d2ff' });
    slide9.addText(team.comp, { x: x + 0.15, y: 1.7, w: 2.7, h: 0.5, fontSize: 10, bold: true, color: 'e94560' });
    slide9.addText(team.role, { x: x + 0.15, y: 2.15, w: 2.7, h: 0.3, fontSize: 9, color: 'a2d2ff' });
    slide9.addText(team.desc, { x: x + 0.15, y: 2.5, w: 2.7, h: 2, fontSize: 10, color: 'ffffff', valign: 'top' });
  });
  
  // Slide 10: End
  const slide10 = pptx.addSlide();
  slide10.background = { path: gradientBg1 };
  slide10.addText('感谢观看', { x: 0.5, y: 1.3, w: 9, h: 1, fontSize: 42, bold: true, color: 'e94560', align: 'center' });
  slide10.addText('刻晴 - 霆霓快雨', { x: 0.5, y: 2.4, w: 9, h: 0.6, fontSize: 24, color: 'ffffff', align: 'center' });
  slide10.addText('「人像是蛾子，总奔着名叫神仙的火光而去。但是我这光是自己点的。」', 
    { x: 1, y: 3.2, w: 8, h: 0.8, fontSize: 14, italic: true, color: 'a2d2ff', align: 'center' });
  slide10.addText('Genshin Impact © miHoYo', { x: 0.5, y: 4.5, w: 9, h: 0.5, fontSize: 14, color: 'ffffff', align: 'center' });
  
  // Add transitions/animations to all slides
  for (let i = 0; i < 10; i++) {
    pptx.slides[i].transition = { type: 'fade', speed: 'fast' };
  }
  
  // Save
  await pptx.writeFile({ fileName: path.join(pptDir, '刻晴角色介绍.pptx') });
  console.log('PPT created successfully!');
}

createPresentation().catch(console.error);
