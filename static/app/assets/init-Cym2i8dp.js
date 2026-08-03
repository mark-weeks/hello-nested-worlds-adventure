import{B as e,N as t,T as n,a as r,c as i,h as a,i as o,l as s,n as c,r as l,y as u,z as d}from"./Shader-CuqW9kUu.js";import{d as f,t as p}from"./Filter-DJ0fTosb.js";import{t as m}from"./getPo2TextureFromSource-DNGA0xNp.js";import{t as h}from"./canvasUtils-BrjqhLLU.js";import{t as g}from"./CanvasPool-DAOHNZzA.js";var _=new u;function v(e,t){t.clear();let n=t.matrix;for(let n=0;n<e.length;n++){let r=e[n];if(r.globalDisplayStatus<7)continue;let i=r.renderGroup??r.parentRenderGroup;t.matrix=i?.isCachedAsTexture?_.copyFrom(i.textureOffsetInverseTransform).append(r.worldTransform):i?._parentCacheAsTextureRenderGroup?_.copyFrom(i._parentCacheAsTextureRenderGroup.inverseWorldTransform).append(r.groupTransform):r.worldTransform,t.addBounds(r.bounds)}return t.matrix=n,t}function y(e){return typeof e.getCanvasFilterString==`function`}var b=class{constructor(){this.skip=!1,this.useClip=!1,this.filters=null,this.container=null,this.bounds=new a,this.cssFilterString=``}},x=class{constructor(e){this._filterStack=[],this._filterStackIndex=0,this._savedStates=[],this._alphaMultiplier=1,this._warnedFilterTypes=new Set,this.renderer=e}push(e){let t=this._pushFilterFrame(),n=e.filterEffect.filters;if(t.skip=!1,t.useClip=!1,t.filters=n,t.container=e.container,t.cssFilterString=``,n.every(e=>!e.enabled)){t.skip=!0;return}let r=[];for(let e of n){if(!e.enabled)continue;if(!y(e)){this._warnUnsupportedFilter(e);continue}let t=e.getCanvasFilterString();if(t===null){this._warnUnsupportedFilter(e);continue}t&&r.push(t)}if(r.length===0){t.skip=!0;return}t.cssFilterString=r.join(` `),this._calculateFilterArea(e,t.bounds),t.useClip=!!e.filterEffect.filterArea;let i=this.renderer.canvasContext.activeContext,a=i.filter||`none`;if(this._savedStates.push({filter:a,alphaMultiplier:this._alphaMultiplier}),t.useClip&&Number.isFinite(t.bounds.width)&&Number.isFinite(t.bounds.height)&&t.bounds.width>0&&t.bounds.height>0){let e=this.renderer.canvasContext.activeResolution||1;i.save(),i.setTransform(1,0,0,1,0,0),i.beginPath(),i.rect(t.bounds.x*e,t.bounds.y*e,t.bounds.width*e,t.bounds.height*e),i.clip()}else t.useClip=!1;t.cssFilterString&&(i.filter=a===`none`?t.cssFilterString:`${a} ${t.cssFilterString}`)}pop(){let e=this._popFilterFrame();if(e.skip)return;let t=this._savedStates.pop();if(!t)return;let n=this.renderer.canvasContext.activeContext;e.useClip?n.restore():n.filter=t.filter,this._alphaMultiplier=t.alphaMultiplier}generateFilteredTexture({texture:e,filters:t}){if(!t?.length||t.every(e=>!e.enabled))return e;let n=[];for(let e of t){if(!e.enabled)continue;if(!y(e)){this._warnUnsupportedFilter(e);continue}let t=e.getCanvasFilterString();if(t===null){this._warnUnsupportedFilter(e);continue}t&&n.push(t)}if(n.length===0)return e;let r=h.getCanvasSource(e);if(!r)return e;let i=e.frame,a=e.source._resolution??e.source.resolution??1,o=i.width,s=i.height,{canvas:c,context:l}=g.getOptimalCanvasAndContext(o,s,a);l.setTransform(1,0,0,1,0,0),l.clearRect(0,0,c.width,c.height),n.length&&(l.filter=n.join(` `));let u=i.x*a,d=i.y*a,f=o*a,p=s*a;return l.drawImage(r,u,d,f,p,0,0,f,p),l.filter=`none`,l.globalAlpha=1,m(c,o,s,a)}_calculateFilterArea(e,t){if(e.renderables?v(e.renderables,t):e.filterEffect.filterArea?(t.clear(),t.addRect(e.filterEffect.filterArea),t.applyMatrix(e.container.worldTransform)):e.container.getFastGlobalBounds(!0,t),e.container){let n=(e.container.renderGroup||e.container.parentRenderGroup)?.cacheToLocalTransform;n&&t.applyMatrix(n)}}_warnUnsupportedFilter(e){let t=e?.constructor?.name||`Filter`;this._warnedFilterTypes.has(t)||(this._warnedFilterTypes.add(t),console.warn(`CanvasRenderer: filter "${t}" is not supported in Canvas2D and will be skipped.`))}get alphaMultiplier(){return this._alphaMultiplier}_pushFilterFrame(){let e=this._filterStack[this._filterStackIndex];return e||=this._filterStack[this._filterStackIndex]=new b,this._filterStackIndex++,e}_popFilterFrame(){return this._filterStackIndex<=0?this._filterStack[0]:(this._filterStackIndex--,this._filterStack[this._filterStackIndex])}destroy(){this._filterStack=null,this._savedStates=null,this._warnedFilterTypes=null,this._alphaMultiplier=1}};x.extension={type:[d.CanvasSystem],name:`filter`};var S=`in vec2 aPosition;
out vec2 vTextureCoord;

uniform vec4 uInputSize;
uniform vec4 uOutputFrame;
uniform vec4 uOutputTexture;

vec4 filterVertexPosition( void )
{
    vec2 position = aPosition * uOutputFrame.zw + uOutputFrame.xy;

    position.x = position.x * (2.0 / uOutputTexture.x) - 1.0;
    position.y = position.y * (2.0*uOutputTexture.z / uOutputTexture.y) - uOutputTexture.z;

    return vec4(position, 0.0, 1.0);
}

vec2 filterTextureCoord( void )
{
    return aPosition * (uOutputFrame.zw * uInputSize.zw);
}

void main(void)
{
    gl_Position = filterVertexPosition();
    vTextureCoord = filterTextureCoord();
}
`,C=`in vec2 vTextureCoord;
out vec4 finalColor;
uniform sampler2D uTexture;
void main() {
    finalColor = texture(uTexture, vTextureCoord);
}
`,w=`struct GlobalFilterUniforms {
  uInputSize: vec4<f32>,
  uInputPixel: vec4<f32>,
  uInputClamp: vec4<f32>,
  uOutputFrame: vec4<f32>,
  uGlobalFrame: vec4<f32>,
  uOutputTexture: vec4<f32>,
};

@group(0) @binding(0) var <uniform> gfu: GlobalFilterUniforms;
@group(0) @binding(1) var uTexture: texture_2d<f32>;
@group(0) @binding(2) var uSampler: sampler;

struct VSOutput {
  @builtin(position) position: vec4<f32>,
  @location(0) uv: vec2<f32>
};

fn filterVertexPosition(aPosition: vec2<f32>) -> vec4<f32>
{
    var position = aPosition * gfu.uOutputFrame.zw + gfu.uOutputFrame.xy;

    position.x = position.x * (2.0 / gfu.uOutputTexture.x) - 1.0;
    position.y = position.y * (2.0 * gfu.uOutputTexture.z / gfu.uOutputTexture.y) - gfu.uOutputTexture.z;

    return vec4(position, 0.0, 1.0);
}

fn filterTextureCoord(aPosition: vec2<f32>) -> vec2<f32>
{
    return aPosition * (gfu.uOutputFrame.zw * gfu.uInputSize.zw);
}

@vertex
fn mainVertex(
  @location(0) aPosition: vec2<f32>,
) -> VSOutput {
  return VSOutput(
   filterVertexPosition(aPosition),
   filterTextureCoord(aPosition)
  );
}

@fragment
fn mainFragment(
  @location(0) uv: vec2<f32>,
) -> @location(0) vec4<f32> {
    return textureSample(uTexture, uSampler, uv);
}
`,T=class extends p{constructor(){let e=o.from({vertex:{source:w,entryPoint:`mainVertex`},fragment:{source:w,entryPoint:`mainFragment`},name:`passthrough-filter`}),t=r.from({vertex:S,fragment:C,name:`passthrough-filter`});super({gpuProgram:e,glProgram:t})}},E=class{constructor(e){this._renderer=e}push(e,t,n){this._renderer.renderPipes.batch.break(n),n.add({renderPipeId:`filter`,canBundle:!1,action:`pushFilter`,container:t,filterEffect:e})}pop(e,t,n){this._renderer.renderPipes.batch.break(n),n.add({renderPipeId:`filter`,action:`popFilter`,canBundle:!1})}execute(e){e.action===`pushFilter`?this._renderer.filter.push(e):e.action===`popFilter`&&this._renderer.filter.pop()}destroy(){this._renderer=null}};E.extension={type:[d.WebGLPipes,d.WebGPUPipes,d.CanvasPipes],name:`filter`};var D=new i({attributes:{aPosition:{buffer:new Float32Array([0,0,1,0,1,1,0,1]),format:`float32x2`,stride:8,offset:0}},indexBuffer:new Uint32Array([0,1,2,0,2,3])}),O=class{constructor(){this.skip=!1,this.inputTexture=null,this.backTexture=null,this.filters=null,this.bounds=new a,this.container=null,this.blendRequired=!1,this.outputRenderSurface=null,this.globalFrame={x:0,y:0,width:0,height:0},this.firstEnabledIndex=-1,this.lastEnabledIndex=-1}},k=class{constructor(e){this._filterStackIndex=0,this._filterStack=[],this._filterGlobalUniforms=new t({uInputSize:{value:new Float32Array(4),type:`vec4<f32>`},uInputPixel:{value:new Float32Array(4),type:`vec4<f32>`},uInputClamp:{value:new Float32Array(4),type:`vec4<f32>`},uOutputFrame:{value:new Float32Array(4),type:`vec4<f32>`},uGlobalFrame:{value:new Float32Array(4),type:`vec4<f32>`},uOutputTexture:{value:new Float32Array(4),type:`vec4<f32>`}}),this._globalFilterBindGroup=new l({}),this.renderer=e}get activeBackTexture(){return this._activeFilterData?.backTexture}push(e){let t=this.renderer,n=e.filterEffect.filters,r=this._pushFilterData();r.skip=!1,r.filters=n,r.container=e.container,r.outputRenderSurface=t.renderTarget.renderSurface;let i=t.renderTarget.renderTarget.colorTexture.source,a=i.resolution,o=i.antialias;if(n.every(e=>!e.enabled)){r.skip=!0;return}let s=r.bounds;if(this._calculateFilterArea(e,s),this._calculateFilterBounds(r,t.renderTarget.rootViewPort,o,a,1),r.skip)return;let c=this._getPreviousFilterData(),l=this._findFilterResolution(a),u=0,d=0;c&&(u=c.bounds.minX,d=c.bounds.minY),this._calculateGlobalFrame(r,u,d,l,i.width,i.height),this._setupFilterTextures(r,s,t,c)}generateFilteredTexture({texture:e,filters:t}){let n=this._pushFilterData();this._activeFilterData=n,n.skip=!1,n.filters=t;let r=e.source,i=r.resolution,a=r.antialias;if(t.every(e=>!e.enabled))return n.skip=!0,e;let o=n.bounds;if(o.addRect(e.frame),this._calculateFilterBounds(n,o.rectangle,a,i,0),n.skip)return e;let c=i;this._calculateGlobalFrame(n,0,0,c,r.width,r.height),n.outputRenderSurface=f.getOptimalTexture(o.width,o.height,n.resolution,n.antialias),n.backTexture=s.EMPTY,n.inputTexture=e,this.renderer.renderTarget.finishRenderPass(),this._applyFiltersToTexture(n,!0);let l=n.outputRenderSurface;return l.source.alphaMode=`premultiplied-alpha`,l}pop(){let e=this.renderer,t=this._popFilterData();t.skip||(e.globalUniforms.pop(),e.renderTarget.finishRenderPass(),this._activeFilterData=t,this._applyFiltersToTexture(t,!1),t.blendRequired&&f.returnTexture(t.backTexture),f.returnTexture(t.inputTexture))}getBackTexture(e,t,n){let r=e.colorTexture.source._resolution,i=f.getOptimalTexture(t.width,t.height,r,!1),a=t.minX,o=t.minY;n&&(a-=n.minX,o-=n.minY),a=Math.floor(a*r),o=Math.floor(o*r);let s=Math.ceil(t.width*r),c=Math.ceil(t.height*r);return this.renderer.renderTarget.copyToTexture(e,i,{x:a,y:o},{width:s,height:c},{x:0,y:0}),i}applyFilter(e,t,n,r){let i=this.renderer,a=this._activeFilterData,o=a.outputRenderSurface===n,s=i.renderTarget.rootRenderTarget.colorTexture.source._resolution,c=this._findFilterResolution(s),l=0,u=0;if(o){let e=this._findPreviousFilterOffset();l=e.x,u=e.y}this._updateFilterUniforms(t,n,a,l,u,c,o,r);let d=e.enabled?e:this._getPassthroughFilter();this._setupBindGroupsAndRender(d,t,i)}calculateSpriteMatrix(e,t){let n=this._activeFilterData,r=e.set(n.inputTexture._source.width,0,0,n.inputTexture._source.height,n.bounds.minX,n.bounds.minY),i=t.worldTransform.copyTo(u.shared),a=t.renderGroup||t.parentRenderGroup;return a&&a.cacheToLocalTransform&&i.prepend(a.cacheToLocalTransform),i.invert(),r.prepend(i),r.scale(1/t.texture.orig.width,1/t.texture.orig.height),r.translate(t.anchor.x,t.anchor.y),r}destroy(){this._passthroughFilter?.destroy(!0),this._passthroughFilter=null}_getPassthroughFilter(){return this._passthroughFilter??=new T,this._passthroughFilter}_setupBindGroupsAndRender(e,t,n){if(n.renderPipes.uniformBatch){let e=n.renderPipes.uniformBatch.getUboResource(this._filterGlobalUniforms);this._globalFilterBindGroup.setResource(e,0)}else this._globalFilterBindGroup.setResource(this._filterGlobalUniforms,0);this._globalFilterBindGroup.setResource(t.source,1),this._globalFilterBindGroup.setResource(t.source.style,2),e.groups[0]=this._globalFilterBindGroup,n.encoder.draw({geometry:D,shader:e,state:e._state,topology:`triangle-list`}),n.type===c.WEBGL&&n.renderTarget.finishRenderPass()}_setupFilterTextures(e,t,n,r){if(e.backTexture=s.EMPTY,e.inputTexture=f.getOptimalTexture(t.width,t.height,e.resolution,e.antialias),e.blendRequired){n.renderTarget.finishRenderPass();let i=n.renderTarget.getRenderTarget(e.outputRenderSurface);e.backTexture=this.getBackTexture(i,t,r?.bounds)}n.renderTarget.bind(e.inputTexture,!0),n.globalUniforms.push({offset:t})}_calculateGlobalFrame(e,t,n,r,i,a){let o=e.globalFrame;o.x=t*r,o.y=n*r,o.width=i*r,o.height=a*r}_updateFilterUniforms(e,t,n,r,i,a,o,c){let l=this._filterGlobalUniforms.uniforms,u=l.uOutputFrame,d=l.uInputSize,f=l.uInputPixel,p=l.uInputClamp,m=l.uGlobalFrame,h=l.uOutputTexture;o?(u[0]=n.bounds.minX-r,u[1]=n.bounds.minY-i):(u[0]=0,u[1]=0),u[2]=e.frame.width,u[3]=e.frame.height,d[0]=e.source.width,d[1]=e.source.height,d[2]=1/d[0],d[3]=1/d[1],f[0]=e.source.pixelWidth,f[1]=e.source.pixelHeight,f[2]=1/f[0],f[3]=1/f[1],p[0]=.5*f[2],p[1]=.5*f[3],p[2]=e.frame.width*d[2]-.5*f[2],p[3]=e.frame.height*d[3]-.5*f[3];let g=this.renderer.renderTarget.rootRenderTarget.colorTexture;m[0]=r*a,m[1]=i*a,m[2]=g.source.width*a,m[3]=g.source.height*a,t instanceof s&&(t.source.resource=null);let _=this.renderer.renderTarget.getRenderTarget(t);this.renderer.renderTarget.bind(t,!!c),t instanceof s?(h[0]=t.frame.width,h[1]=t.frame.height):(h[0]=_.width,h[1]=_.height),h[2]=_.isRoot?-1:1,this._filterGlobalUniforms.update()}_findFilterResolution(e){let t=this._filterStackIndex-1;for(;t>0&&this._filterStack[t].skip;)--t;return t>0&&this._filterStack[t].inputTexture?this._filterStack[t].inputTexture.source._resolution:e}_findPreviousFilterOffset(){let e=0,t=0,n=this._filterStackIndex;for(;n>0;){n--;let r=this._filterStack[n];if(!r.skip){e=r.bounds.minX,t=r.bounds.minY;break}}return{x:e,y:t}}_calculateFilterArea(e,t){if(e.renderables?v(e.renderables,t):e.filterEffect.filterArea?(t.clear(),t.addRect(e.filterEffect.filterArea),t.applyMatrix(e.container.worldTransform)):e.container.getFastGlobalBounds(!0,t),e.container){let n=(e.container.renderGroup||e.container.parentRenderGroup).cacheToLocalTransform;n&&t.applyMatrix(n)}}_applyFiltersToTexture(e,t){let n=e.inputTexture,r=e.bounds,i=e.filters,a=e.firstEnabledIndex,o=e.lastEnabledIndex;if(this._globalFilterBindGroup.setResource(n.source.style,2),this._globalFilterBindGroup.setResource(e.backTexture.source,3),a===o)i[a].apply(this,n,e.outputRenderSurface,t);else{let n=e.inputTexture,s=f.getOptimalTexture(r.width,r.height,n.source._resolution,!1),c=s;for(let e=a;e<o;e++){let t=i[e];if(!t.enabled)continue;t.apply(this,n,c,!0);let r=n;n=c,c=r}i[o].apply(this,n,e.outputRenderSurface,t),f.returnTexture(s)}}_calculateFilterBounds(e,t,r,i,a){let o=this.renderer,s=e.bounds,c=e.filters,l=1/0,u=0,d=!0,f=!1,p=!1,m=!0,h=-1,g=-1;for(let e=0;e<c.length;e++){let t=c[e];if(t.enabled){if(h===-1&&(h=e),g=e,l=Math.min(l,t.resolution===`inherit`?i:t.resolution),u+=t.padding,t.antialias===`off`?d=!1:t.antialias===`inherit`&&(d&&=r),t.clipToViewport||(m=!1),!(t.compatibleRenderers&o.type)){p=!1;break}if(t.blendRequired&&!(o.backBuffer?.useBackBuffer??!0)){n("Blend filter requires backBuffer on WebGL renderer to be enabled. Set `useBackBuffer: true` in the renderer options."),p=!1;break}p=!0,f||=t.blendRequired}}if(!p){e.skip=!0;return}if(m&&s.fitBounds(0,t.width/i,0,t.height/i),s.scale(l).ceil().scale(1/l).pad((u|0)*a),!s.isPositive){e.skip=!0;return}e.antialias=d,e.resolution=l,e.blendRequired=f,e.firstEnabledIndex=h,e.lastEnabledIndex=g}_popFilterData(){return this._filterStackIndex--,this._filterStack[this._filterStackIndex]}_getPreviousFilterData(){let e,t=this._filterStackIndex-1;for(;t>0&&(t--,e=this._filterStack[t],e.skip););return e}_pushFilterData(){let e=this._filterStack[this._filterStackIndex];return e||=this._filterStack[this._filterStackIndex]=new O,this._filterStackIndex++,e}};k.extension={type:[d.WebGLSystem,d.WebGPUSystem],name:`filter`},e.add(k,x),e.add(E);