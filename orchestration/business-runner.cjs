// Factory-owned runner. Test input is declarative data, never executable code.
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.FACTORY_PLAYWRIGHT_MODULE || process.env.PLAYWRIGHT_MODULE || 'playwright');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const output = process.argv[3];
const origin = new URL(input.url).origin;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Only local previews are permitted');
(async()=>{
 const browser=await chromium.launch({headless:true,...((process.env.FACTORY_BROWSER)?{executablePath:process.env.FACTORY_BROWSER}:{})});
 const deadline=setTimeout(()=>browser.close(),120000);
 const results=[];
 try{
  for(const width of [1440,390])for(const [index,scenario] of input.cases.entries()){
   const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block',acceptDownloads:false});
   await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
   await context.routeWebSocket('**/*',socket=>socket.close());
   const page=await context.newPage();page.setDefaultTimeout(4000);page.setDefaultNavigationTimeout(15000);
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const result={name:scenario.name,width,passed:false,steps:0,screenshot:`case-${index}-${width}.png`};
   try{
    let response=await page.goto(input.url,{waitUntil:'domcontentloaded'});
    if(!response||response.status()>=400)throw Error('Initial page returned an error');
    let assertions=0;
    for(const step of scenario.steps){
     switch(step.action){
      case 'visit': {
       const url=new URL(step.target,origin);
       if(url.origin!==origin||!step.target.startsWith('/')||step.target.startsWith('//'))throw Error('Navigation must stay in preview');
       response=await page.goto(url.href,{waitUntil:'domcontentloaded'});
       if(!response||response.status()>=400)throw Error('Page returned an error');break;
      }
      case 'click': {
       const button=page.getByRole('button',{name:step.target,exact:true});
       const link=page.getByRole('link',{name:step.target,exact:true});
       await (await link.count()===1&&await button.count()===0?link:button).click();break;
      }
      case 'fill': await page.getByLabel(step.target,{exact:true}).fill(step.value);break;
      case 'text': await page.getByText(step.target,{exact:true}).waitFor({state:'visible'});assertions++;break;
      case 'value': {
       const field=page.getByLabel(step.target,{exact:true});await field.waitFor({state:'visible'});
       const deadline=Date.now()+4000;
       while(await field.inputValue()!==step.value){if(Date.now()>=deadline)throw Error('Field value differs from expectation');await new Promise(resolve=>setTimeout(resolve,100))}
       assertions++;break;
      }
      case 'reload': await page.reload({waitUntil:'domcontentloaded'});break;
      default: throw Error('Unknown test action');
     }
     result.steps++;
     if(new URL(page.url()).origin!==origin)throw Error('Page left preview origin');
    }
    if(!assertions)throw Error('A business test must assert an observable result');
    if(errors.length)throw Error('Browser error: '+errors[0]);
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Horizontal page overflow');
    result.passed=true;
   }catch(error){result.error=String(error.message).slice(0,2000)}
   finally{
    try{await page.screenshot({path:path.join(output,result.screenshot),fullPage:true,timeout:5000})}catch{result.screenshot=null}
    results.push(result);await context.close();
   }
  }
 }finally{clearTimeout(deadline);await browser.close();fs.writeFileSync(path.join(output,'business-report.json'),JSON.stringify({passed:results.length===input.cases.length*2&&results.every(r=>r.passed),cases:results},null,2));}
 if(!results.every(r=>r.passed))process.exitCode=1;
})().catch(error=>{console.error(error.message);process.exitCode=1});
