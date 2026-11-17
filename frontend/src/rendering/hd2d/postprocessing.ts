import * as THREE from 'three'

// 景深仅改变场景画面，界面文字由DOM绘制，透明人物与建筑共用同一次绘制的深度。
export function createScenePost() {
  const target = new THREE.WebGLRenderTarget(1, 1, {
    depthTexture: new THREE.DepthTexture(1, 1, THREE.UnsignedIntType),
  })
  const material = new THREE.ShaderMaterial({
    uniforms: { colorMap: { value: target.texture }, depthMap: { value: target.depthTexture },
      resolution: { value: new THREE.Vector2(1, 1) }, focus: { value: .45 } },
    depthTest: false, depthWrite: false,
    vertexShader: 'varying vec2 uvOut;void main(){uvOut=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader: `
      uniform sampler2D colorMap; uniform sampler2D depthMap;
      uniform vec2 resolution; uniform float focus; varying vec2 uvOut;
      void main(){
        float depth=texture2D(depthMap,uvOut).x;
        float blur=smoothstep(.06,.25,abs(depth-focus))*1.1;
        vec2 stepSize=blur/resolution;
        vec4 color=texture2D(colorMap,uvOut)*4.;
        color+=texture2D(colorMap,uvOut+vec2(stepSize.x,0.));
        color+=texture2D(colorMap,uvOut-vec2(stepSize.x,0.));
        color+=texture2D(colorMap,uvOut+vec2(0.,stepSize.y));
        color+=texture2D(colorMap,uvOut-vec2(0.,stepSize.y));
        gl_FragColor=color/8.;
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  })
  const scene = new THREE.Scene()
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material)
  scene.add(quad)
  const camera = new THREE.Camera()
  return {
    resize(width: number, height: number) { target.setSize(width, height); material.uniforms.resolution!.value.set(width, height) },
    render(renderer: THREE.WebGLRenderer, world: THREE.Scene, view: THREE.OrthographicCamera, center: THREE.Vector3) {
      const distance = -center.clone().applyMatrix4(view.matrixWorldInverse).z
      material.uniforms.focus!.value = (distance - view.near) / (view.far - view.near)
      renderer.setRenderTarget(target); renderer.render(world, view)
      renderer.setRenderTarget(null); renderer.render(scene, camera)
    },
    dispose() { target.dispose(); quad.geometry.dispose(); material.dispose() },
  }
}
