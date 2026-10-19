const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1487,height:1058}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:'+fs.readFileSync('work/ui_test_port.txt','utf8').trim());
 await page.waitForFunction(()=>document.documentElement.dataset.theme);
 await page.getByRole('button',{name:'Switch to day mode'}).click();
 await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
 await page.screenshot({animations:'disabled',path:'work/workspace-day.png'});
 const rects=()=>Array.from(document.querySelectorAll('.app-sidebar,.app-header,.config-panel,.status-panel,.log-panel,.theme-switch,input,.tab-btn')).map(e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]});
 const day=await page.evaluate(rects);
 await page.getByRole('button',{name:'Switch to night mode'}).click();
 await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');
 assert.deepEqual(await page.evaluate(rects),day,'Theme must change only colors, not layout');
 await page.screenshot({animations:'disabled',path:'work/workspace-night.png'});
 for(const size of [{width:1280,height:900},{width:800,height:600}]){
  await page.setViewportSize(size);
  await page.screenshot({animations:'disabled',path:`work/workspace-${size.width}.png`});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const theme=await page.locator('.theme-switch').boundingBox();assert(theme.y+theme.height<=size.height);
 }
 assert.deepEqual(errors,[]);
 console.log('PASS: identical day/night geometry, no page overflow, theme controls visible at 1487, 1280 and 800 pixels, no script errors.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
