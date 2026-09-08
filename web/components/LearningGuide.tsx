'use client';
import { useState } from 'react';
import { ArrowRight, BookOpen, Check } from 'lucide-react';
import type { Settings } from '@/lib/ocean';
import './services.css';

export const lessons = [
  {title: 'Dive through the water column', action: 'Move the Depth slice slider from 0 m to 300 m. Compare the colors using the scale beneath the scene.', explanation: 'A surface map shows one depth. A water-column view lets you see how temperature changes beneath it. This lesson uses an explicitly synthetic ocean to make the pattern easy to inspect.', question: 'Does a blue patch always mean the same temperature?', answers: ['No. Read the colorbar and its units.', 'Yes. Blue always means 10°C.'], correct: 0, feedback: 'Colors depend on the chosen range and palette. The numerical colorbar gives them meaning.', settings: {variable:'temperature', mode:'slice', min:5, max:31, depth:0, palette:'thermal'}},
  {title: 'Reveal a hidden layer', action: 'Use the Isosurface value slider to change the threshold. Rotate the scene and compare its shape.', explanation: 'An isosurface joins locations with the same value. It helps reveal structures inside the water column. A surface may disappear when the threshold is outside the available data.', question: 'What does the temperature surface represent?', answers: ['A solid wall in the ocean.', 'Locations sharing the chosen temperature.'], correct: 1, feedback: 'It is a mathematical surface in a sampled field. It is not a material boundary or a tracked water parcel.', settings: {variable:'temperature', mode:'isosurface', min:5, max:31, iso:20, palette:'thermal'}},
  {title: 'Read the current field', action: 'Follow the moving dots, then change the selected depth. Notice how circulation changes through the water column.', explanation: 'These lines follow horizontal current vectors in one selected time and depth. Animated dots show direction along those lines; they are not forecasts of where a person, vessel or pollutant will travel.', question: 'Can these lines predict a search-and-rescue trajectory?', answers: ['Yes. The animation predicts the future.', 'No. They use a frozen field at one depth.'], correct: 1, feedback: 'Search-and-rescue requires time-evolving currents, winds, drift physics and validated uncertainty. These lines explain the current field.', settings: {variable:'u', mode:'slice', min:-1, max:1, palette:'balance', depth:100, currents:true, flow:true}},
  {title: 'Check a measurement', action: 'Select ARGO-01 in the scene. Compare the observed and model curves, then switch from strict to lenient quality.', explanation: 'A model estimates a field across a grid. An instrument samples selected locations and times. Quality flags and matching times determine which measurements can enter the comparison.', question: 'Does close agreement prove independent forecast skill?', answers: ['No. The model may have used the same observations.', 'Yes. A small difference is proof.'], correct: 0, feedback: 'Independent validation must account for assimilation and use enough independent cases. A single matching profile is useful evidence with limits.', settings: {variable:'temperature', mode:'volume', min:5, max:31, palette:'thermal', profile:'DEMO-ARGO-01', instruments:true}},
] satisfies {title:string; action:string; explanation:string; question:string; answers:string[]; correct:number; feedback:string; settings:Partial<Settings>}[];

export default function LearningGuide({step, onStep, onExit}: {step:number; onStep:(step:number)=>void; onExit:()=>void}) {
  const [answer, setAnswer] = useState<number | null>(null);
  const lesson = lessons[step];
  function choose(i:number) {setAnswer(null); onStep(i);}
  return <section className="learning-guide" aria-label="Ocean classroom">
    <div className="lesson-progress"><span className="eyebrow"><BookOpen size={15}/> OCEAN CLASSROOM · {step+1} / {lessons.length}</span><button onClick={onExit}>Exit classroom</button></div>
    <fieldset className="lesson-tabs" aria-label="Choose a lesson">{lessons.map((l,i)=><button key={l.title} aria-pressed={step===i} onClick={()=>choose(i)}>{i+1}. {l.title}</button>)}</fieldset>
    <div className="lesson-content"><div><h2>{lesson.title}</h2><p>{lesson.explanation}</p><p className="lesson-action">{lesson.action}</p></div><div className="lesson-question"><strong>{lesson.question}</strong><div>{lesson.answers.map((a,i)=><button key={a} aria-pressed={answer===i} onClick={()=>setAnswer(i)}>{answer===i && i===lesson.correct && <Check size={15}/>} {a}</button>)}</div>{answer!==null && <output>{answer===lesson.correct?'Correct. ':'Try the other answer. '}{lesson.feedback}</output>}<button className="lesson-next" onClick={()=>choose((step+1)%lessons.length)}>{step===lessons.length-1?'Start again':'Next lesson'} <ArrowRight size={15}/></button></div></div>
  </section>;
}


