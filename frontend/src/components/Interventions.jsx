import {useEffect,useRef} from 'react';
import {betaKey} from '../auth.js';
import '../../../static/interventions.js';
export default function Interventions({node,seed,onJump,onNodeChanged,onEnsurePosition}) {
  const ref=useRef(null);
  useEffect(()=>{ ref.current.context={node,seed,key:betaKey(),jump:onJump,changed:onNodeChanged,ensure:onEnsurePosition}; },[node,seed,onJump,onNodeChanged,onEnsurePosition]);
  return <enfolded-interventions ref={ref} />;
}
