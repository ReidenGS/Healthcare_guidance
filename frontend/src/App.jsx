import React, { useState, useEffect } from 'react';
import {
  checkInsurance,
  createBookingIntent,
  createSession,
  geocodeLocation,
  getBookingRecords,
  getRecommendation,
  getSummary,
  searchProviders,
  sendRecommendationFeedback,
  submitAnswers,
  getStoredApiKeys,
  saveApiKeys,
} from './api';
import {
  ChevronRight,
  MapPin,
  Phone,
  Clock,
  ShieldAlert,
  CheckCircle2,
  ArrowRight,
  Info,
  Stethoscope,
  ChevronLeft,
  ThumbsDown,
  ThumbsUp,
  CalendarCheck,
  User,
  RefreshCcw,
  ShieldCheck,
  Building2,
  Search,
  DollarSign,
  XCircle,
  ExternalLink,
  Lock,
  FileText,
  Activity,
  Bot,
  Settings,
  Eye,
  EyeOff,
  KeyRound,
} from 'lucide-react';

/**
 * ==========================================
 * 1. Base UI Components
 * ==========================================
 */

const DISCLAIMER = "This service provides AI care navigation guidance and is not a medical diagnosis.";

// Top progress bar component
export const ProgressBar = ({ currentStep }) => {
  const steps = [
    { statusList: ['PROFILE'], label: 'Profile', index: 0 },
    { statusList: ['INTAKE', 'FOLLOW_UP', 'TRIAGE_READY'], label: 'Symptoms', index: 1 },
    { statusList: ['PROVIDER_MATCHED', 'INSURANCE', 'INSURANCE_RESULT'], label: 'Matching', index: 2 },
    { statusList: ['BOOKING', 'COMPLETED'], label: 'Confirm', index: 3 }
  ];

  const currentIndex = steps.find(s => s.statusList.includes(currentStep))?.index || 0;

  return (
    <div className="flex items-center justify-between w-full">
      {steps.map((step, idx) => {
        const isActive = idx === currentIndex;
        const isPast = idx < currentIndex;
        return (
          <React.Fragment key={idx}>
            <div className="flex flex-col items-center flex-1 group">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${
                isActive ? 'bg-blue-600 text-white ring-4 ring-blue-50 shadow-md scale-110' : 
                isPast ? 'bg-green-500 text-white shadow-sm' : 'bg-gray-100 text-gray-400'
              }`}>
                {isPast ? <CheckCircle2 size={20} /> : idx + 1}
              </div>
              <span className={`text-xs mt-3 font-bold transition-colors ${isActive ? 'text-blue-600' : 'text-gray-400'}`}>
                {step.label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div className={`h-[3px] flex-1 mx-4 rounded-full transition-colors duration-500 ${isPast ? 'bg-green-500' : 'bg-gray-100'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

/**
 * ==========================================
 * 2. Page-level View Components
 * ==========================================
 */

// ==========================================
// AI Analyzing Overlay
// ==========================================

const ANALYZING_MESSAGES = {
  default: [
    'Analyzing your symptoms…',
    'Reviewing medical knowledge base…',
    'Identifying relevant specialists…',
    'Evaluating risk indicators…',
    'Finalizing your assessment…',
  ],
  FOLLOW_UP: [
    'Processing your responses…',
    'Refining the diagnosis path…',
    'Updating confidence score…',
    'Generating next questions…',
  ],
  PROVIDER_MATCHED: [
    'Searching nearby clinics…',
    'Filtering by specialty…',
    'Checking availability…',
    'Ranking results by proximity…',
  ],
  INSURANCE: [
    'Verifying coverage details…',
    'Estimating out-of-pocket costs…',
    'Checking in-network status…',
  ],
  BOOKING: [
    'Preparing your booking details…',
    'Confirming provider information…',
  ],
};

export const AIAnalyzingOverlay = ({ currentView = 'default' }) => {
  const messages = ANALYZING_MESSAGES[currentView] || ANALYZING_MESSAGES.default;
  const [msgIdx, setMsgIdx] = useState(0);
  const [textVisible, setTextVisible] = useState(true);

  useEffect(() => {
    const cycle = setInterval(() => {
      setTextVisible(false);
      setTimeout(() => {
        setMsgIdx(prev => (prev + 1) % messages.length);
        setTextVisible(true);
      }, 350);
    }, 2400);
    return () => clearInterval(cycle);
  }, [messages.length]);

  return (
    <>
      <style>{`
        @keyframes ai-spin-cw   { from { transform: rotate(0deg);   } to { transform: rotate(360deg);  } }
        @keyframes ai-spin-ccw  { from { transform: rotate(360deg); } to { transform: rotate(0deg);    } }
        @keyframes ai-pulse-ring { 0%,100% { opacity:.25; transform:scale(1);    }  50% { opacity:.6; transform:scale(1.06); } }
        @keyframes ai-glow      { 0%,100% { box-shadow:0 0 18px 4px rgba(99,102,241,.25); } 50% { box-shadow:0 0 32px 10px rgba(99,102,241,.45); } }
        @keyframes ai-fadein    { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:translateY(0); } }
        @keyframes ai-dot       { 0%,80%,100% { transform:scale(.6); opacity:.4; } 40% { transform:scale(1); opacity:1; } }
        .ai-spin-cw   { animation: ai-spin-cw   3s   linear        infinite; }
        .ai-spin-cw2  { animation: ai-spin-cw   1.8s linear        infinite; }
        .ai-spin-ccw  { animation: ai-spin-ccw  2.4s linear        infinite; }
        .ai-pulse-ring{ animation: ai-pulse-ring 2.5s ease-in-out  infinite; }
        .ai-glow      { animation: ai-glow      2.5s ease-in-out  infinite; }
        .ai-fadein    { animation: ai-fadein     .35s ease-out     forwards; }
        .ai-dot-1     { animation: ai-dot 1.4s  .0s  ease-in-out  infinite; }
        .ai-dot-2     { animation: ai-dot 1.4s  .2s  ease-in-out  infinite; }
        .ai-dot-3     { animation: ai-dot 1.4s  .4s  ease-in-out  infinite; }
      `}</style>

      {/* Full-panel overlay */}
      <div className="absolute inset-0 z-50 flex items-center justify-center"
           style={{ background: 'rgba(252,253,253,0.92)', backdropFilter: 'blur(6px)', borderRadius: 'inherit' }}>

        <div className="flex flex-col items-center gap-7 select-none">

          {/* ── Concentric ring animation ── */}
          <div className="relative w-32 h-32 flex items-center justify-center">

            {/* Outermost slow-pulse ring */}
            <div className="absolute inset-0 rounded-full border-2 border-indigo-100 ai-pulse-ring" />

            {/* Outer spinning arc — clockwise */}
            <div className="absolute inset-[4px] rounded-full"
                 style={{ border: '3px solid transparent',
                          borderTopColor: '#818cf8', borderRightColor: '#a5b4fc',
                          borderRadius: '9999px' }}
                 // eslint-disable-next-line react/no-unknown-property
                 data-class="ai-spin-cw">
              <div className="w-full h-full rounded-full ai-spin-cw" style={{border:'3px solid transparent', borderTopColor:'#818cf8', borderRightColor:'#a5b4fc'}} />
            </div>

            {/* Middle arc — counter-clockwise */}
            <div className="absolute inset-[14px] rounded-full ai-spin-ccw"
                 style={{ border: '2.5px solid transparent',
                          borderTopColor: '#6366f1', borderLeftColor: '#4f46e5' }} />

            {/* Inner arc — faster CW */}
            <div className="absolute inset-[24px] rounded-full ai-spin-cw2"
                 style={{ border: '2px solid transparent',
                          borderTopColor: '#7c3aed', borderRightColor: '#8b5cf6' }} />

            {/* Center glowing icon */}
            <div className="absolute inset-[34px] rounded-full ai-glow flex items-center justify-center"
                 style={{ background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 50%, #7c3aed 100%)' }}>
              <Bot size={18} color="white" strokeWidth={2.5} />
            </div>
          </div>

          {/* ── Text block ── */}
          <div className="text-center space-y-2 min-h-[52px] flex flex-col items-center justify-center">
            <p className="text-[17px] font-black text-gray-900 tracking-tight">AI is analyzing</p>
            <div className="h-5 flex items-center justify-center">
              {textVisible && (
                <span className="text-sm text-indigo-500 font-semibold ai-fadein">{messages[msgIdx]}</span>
              )}
            </div>
          </div>

          {/* ── Three bouncing dots ── */}
          <div className="flex gap-[7px] items-center">
            <span className="block w-2 h-2 rounded-full bg-indigo-400 ai-dot-1" />
            <span className="block w-2.5 h-2.5 rounded-full bg-indigo-500 ai-dot-2" />
            <span className="block w-2 h-2 rounded-full bg-indigo-400 ai-dot-3" />
          </div>

          {/* ── Subtle badge ── */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-[11px] font-bold text-indigo-400 tracking-wide uppercase">GPT-4o · Tavily Search</span>
          </div>

        </div>
      </div>
    </>
  );
};

// A0. Profile view — collected before symptom intake
export const ProfileView = ({ onNext }) => {
  const [detailAddress, setDetailAddress] = useState('');
  const [city, setCity] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [age, setAge] = useState('');
  const [sex, setSex] = useState('');
  const [insurancePlan, setInsurancePlan] = useState('');
  const [locationError, setLocationError] = useState('');
  const [pastBookings, setPastBookings] = useState([]);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('healthcare_bookings') || '[]');
      setPastBookings(stored);
    } catch (_) {}
  }, []);

  const clearBookings = () => {
    localStorage.removeItem('healthcare_bookings');
    setPastBookings([]);
  };

  const hasLocationInput = Boolean(detailAddress.trim() || city.trim() || zipCode.trim());
  const isValid = age && sex;

  const formatDateTime = (iso) => {
    try {
      return new Date(iso).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (_) { return iso; }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500 max-w-2xl mx-auto">

      {/* My Appointments panel — only shown when bookings exist */}
      {pastBookings.length > 0 && (
        <div className="bg-white border border-green-100 rounded-[2rem] p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CalendarCheck size={20} className="text-green-600" />
              <span className="font-bold text-gray-900 text-base">My Appointments</span>
              <span className="text-xs font-bold bg-green-100 text-green-700 px-2 py-0.5 rounded-full">{pastBookings.length}</span>
            </div>
            <button onClick={clearBookings} className="text-xs text-gray-400 hover:text-red-500 font-medium transition-colors">
              Clear all
            </button>
          </div>

          <div className="space-y-3">
            {pastBookings.map((b, i) => (
              <div key={b.booking_intent_id || i} className="bg-gray-50 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-gray-900 text-sm truncate">{b.provider_name}</p>
                  {b.provider_address && (
                    <p className="text-xs text-gray-400 truncate mt-0.5">{b.provider_address}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5">
                    {b.department && (
                      <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-lg">{b.department}</span>
                    )}
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      <Clock size={11} /> {formatDateTime(b.preferred_time)}
                    </span>
                  </div>
                </div>
                <span className="text-[11px] font-bold text-green-700 bg-green-100 px-3 py-1 rounded-full shrink-0 self-start sm:self-center">
                  {b.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="text-center pt-4">
        <div className="w-16 h-16 bg-blue-50 text-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm">
          <User size={32} />
        </div>
        <h1 className="text-3xl font-black text-gray-900 tracking-tight">Let's get started</h1>
        <p className="text-gray-500 mt-3 text-base">A few quick details help AI route you to the right specialist and find nearby clinics.</p>
      </div>

      {/* Location block */}
      <div className="bg-white p-8 rounded-[2rem] border border-gray-100 shadow-sm space-y-5 relative overflow-hidden group">
        <div className="absolute top-0 left-0 w-1.5 h-full bg-blue-500 rounded-l-[2rem] opacity-0 group-hover:opacity-100 transition-opacity"></div>
        <p className="text-base font-bold text-gray-800 flex items-center gap-2">
          <MapPin size={18} className="text-blue-500" /> Your location
        </p>
        <div>
          <label className="block text-sm font-bold text-gray-600 mb-2">
            Detail address
          </label>
          <input
            type="text"
            placeholder="e.g. 5th Ave, Apt 7B"
            value={detailAddress}
            onChange={(e) => setDetailAddress(e.target.value)}
            className="w-full p-4 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none text-gray-800 bg-gray-50/50 hover:bg-white transition-all text-base placeholder:text-gray-300"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block text-sm font-bold text-gray-600 mb-2">
                City / State
              </label>
              <input
                type="text"
                placeholder="e.g. Jersey City or New Jersey"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full p-4 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none text-gray-800 bg-gray-50/50 hover:bg-white transition-all text-base placeholder:text-gray-300"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-gray-600 mb-2">
                ZIP code
              </label>
              <input
                type="text"
                placeholder="e.g. 10001"
                value={zipCode}
                onChange={(e) => setZipCode(e.target.value)}
                className="w-full p-4 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none text-gray-800 bg-gray-50/50 hover:bg-white transition-all text-base placeholder:text-gray-300"
              />
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">Enter any one of these fields. We convert what you provide to latitude/longitude for nearby clinic search.</p>
          {locationError && (
            <p className="text-xs text-red-500 mt-2 font-semibold">{locationError}</p>
          )}
        </div>
      </div>

      {/* Profile block */}
      <div className="bg-white p-8 rounded-[2rem] border border-gray-100 shadow-sm space-y-5 relative overflow-hidden group">
        <div className="absolute top-0 left-0 w-1.5 h-full bg-indigo-400 rounded-l-[2rem] opacity-0 group-hover:opacity-100 transition-opacity"></div>
        <p className="text-base font-bold text-gray-800 flex items-center gap-2">
          <Activity size={18} className="text-indigo-400" /> Basic patient info
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-bold text-gray-600 mb-2">Age <span className="text-red-400">*</span></label>
            <input
              type="number" min="1" max="120"
              placeholder="e.g. 35"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className="w-full p-4 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-400 outline-none text-gray-800 bg-gray-50/50 hover:bg-white transition-all text-base placeholder:text-gray-300"
            />
          </div>
          <div>
            <label className="block text-sm font-bold text-gray-600 mb-2">Biological sex <span className="text-red-400">*</span></label>
            <select
              value={sex}
              onChange={(e) => setSex(e.target.value)}
              className="w-full p-4 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-400 outline-none text-gray-800 bg-gray-50/50 hover:bg-white transition-all text-base"
            >
              <option value="">Select…</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other / Prefer not to say</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-600 mb-2">Insurance plan <span className="text-gray-400 font-normal">(optional)</span></label>
          <input
            type="text"
            placeholder="e.g. Aetna PPO, Blue Cross, Uninsured…"
            value={insurancePlan}
            onChange={(e) => setInsurancePlan(e.target.value)}
            className="w-full p-4 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-400 outline-none text-gray-800 bg-gray-50/50 hover:bg-white transition-all text-base placeholder:text-gray-300"
          />
        </div>
      </div>

      <button
        disabled={!isValid}
        onClick={() => {
          if (!hasLocationInput) {
            setLocationError('Please enter at least one location field, or allow GPS location.');
            return;
          }
          setLocationError('');
          onNext?.({
            detailAddress: detailAddress.trim(),
            city: city.trim(),
            zipCode: zipCode.trim(),
            age: parseInt(age) || 0,
            sex,
            insurancePlan: insurancePlan.trim(),
          });
        }}
        className="w-full bg-[#829cd0] hover:bg-blue-600 text-white font-bold py-5 rounded-[1.5rem] flex items-center justify-center gap-2 transition-all duration-300 shadow-xl shadow-blue-500/20 disabled:opacity-50 disabled:shadow-none active:scale-[0.98] text-lg"
      >
        Continue to symptoms
        <ArrowRight size={24} />
      </button>
    </div>
  );
};

// A. Intake view (Stage 1)
export const IntakeView = ({ onSubmit, initialComplaint = "", initialSeverity = 5 }) => {
  const [complaint, setComplaint] = useState(initialComplaint);
  const [severity, setSeverity] = useState(initialSeverity);

  return (
    <div className="space-y-8 animate-in fade-in duration-500 max-w-2xl mx-auto">
      <div className="text-center pt-4">
        <h1 className="text-3xl font-black text-gray-900 tracking-tight">Describe your symptoms</h1>
        <p className="text-gray-500 mt-3 text-base">Tell us what's bothering you. AI will assess risk and recommend the right specialist.</p>
      </div>

      <div className="bg-white p-8 rounded-[2rem] border border-gray-100 shadow-sm space-y-8 relative overflow-hidden group">
        <div className="absolute top-0 left-0 w-1.5 h-full bg-blue-500 rounded-l-[2rem] opacity-0 group-hover:opacity-100 transition-opacity"></div>
        <div>
          <label className="block text-base font-bold text-gray-800 mb-4">Primary symptom description</label>
          <textarea
            className="w-full p-5 rounded-2xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all h-40 text-gray-800 resize-none text-base placeholder:text-gray-300 bg-gray-50/50 hover:bg-white"
            placeholder="Describe your discomfort in detail, for example: I have had dizziness since yesterday afternoon with nausea and no improvement after medication."
            value={complaint}
            onChange={(e) => setComplaint(e.target.value)}
          />
        </div>

        <div>
          <div className="flex justify-between items-end mb-4">
            <label className="block text-base font-bold text-gray-800">Pain score</label>
            <span className={`text-2xl font-black ${severity > 7 ? 'text-red-500' : severity > 4 ? 'text-amber-500' : 'text-green-500'}`}>
              {severity} / 10
            </span>
          </div>
          <input
            type="range" min="0" max="10"
            className="w-full h-3 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 focus:outline-none focus:ring-4 focus:ring-blue-500/30"
            value={severity}
            onChange={(e) => setSeverity(parseInt(e.target.value))}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-3 font-bold px-1">
            <span>0 - No pain</span>
            <span>5 - Moderate discomfort</span>
            <span>10 - Severe unbearable pain</span>
          </div>
        </div>
      </div>

      <button
        disabled={!complaint}
        onClick={() => onSubmit?.({ complaint, severity })}
        className="w-full bg-[#829cd0] hover:bg-blue-600 text-white font-bold py-5 rounded-[1.5rem] flex items-center justify-center gap-2 transition-all duration-300 shadow-xl shadow-blue-500/20 disabled:opacity-50 disabled:shadow-none active:scale-[0.98] text-lg"
      >
        Submit and run AI assessment
        <ArrowRight size={24} />
      </button>
    </div>
  );
};

// A2. Guided follow-up view (Stage 1.5)
export const FollowUpView = ({ questions = [], confidence = 0.65, onSubmit }) => {
  const [selected, setSelected] = useState([]);
  const [noneOfAbove, setNoneOfAbove] = useState(false);
  const [additional, setAdditional] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const toggle = (id) => {
    setNoneOfAbove(false); // deselect "none" when any symptom is chosen
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const toggleNoneOfAbove = () => {
    setNoneOfAbove(prev => !prev);
    setSelected([]); // clear all symptom selections
  };

  return (
    <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 max-w-2xl mx-auto pt-4">
      {/* Dynamic confidence bar */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2 text-slate-600">
          <Activity size={18} className="text-blue-500" />
          <span className="text-sm font-bold tracking-wide">AI confidence assessment in progress...</span>
        </div>
        <div className="flex items-center gap-4 w-1/2">
          <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden shadow-inner">
            <div className="h-full rounded-full transition-all duration-1000 ease-out bg-blue-500" style={{width: `${confidence * 100}%`}} />
          </div>
          <span className="text-sm font-black text-slate-700">{Math.round(confidence * 100)}%</span>
        </div>
      </div>

      <div className={`flex items-start gap-4 transition-all duration-700 transform ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
        <div className="p-4 bg-blue-100 rounded-2xl text-blue-600 shrink-0 shadow-sm border border-blue-200/50">
          <Bot size={28} className="animate-pulse" />
        </div>
        <div className="bg-white border border-gray-200 p-5 rounded-2xl rounded-tl-sm text-gray-800 shadow-sm">
          <p className="font-bold text-base leading-relaxed text-gray-800">
            To improve recommendation accuracy (target confidence &gt; 80%), do you have any of these symptoms?
          </p>
          <p className="text-sm text-gray-500 mt-1">Select all options that apply to you.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {questions.map((q, i) => {
          const isSelected = selected.includes(q.id);
          return (
            <button
              key={q.id} onClick={() => toggle(q.id)} style={{ transitionDelay: `${i * 100}ms` }}
              className={`p-5 text-left rounded-[1.2rem] border-2 transition-all duration-300 transform ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'} ${isSelected ? 'border-blue-500 bg-blue-50/50 shadow-md scale-[1.02]' : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-sm'}`}
            >
              <div className="flex justify-between items-center">
                <span className={`font-bold text-base ${isSelected ? 'text-blue-700' : 'text-gray-700'}`}>{q.text}</span>
                <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${isSelected ? 'border-blue-500 bg-blue-500' : 'border-gray-300'}`}>
                  {isSelected && <CheckCircle2 size={16} className="text-white" />}
                </div>
              </div>
            </button>
          );
        })}

        {/* None of the above — spans full width, always last */}
        <button
          onClick={toggleNoneOfAbove}
          style={{ transitionDelay: `${questions.length * 100}ms` }}
          className={`sm:col-span-2 p-5 text-left rounded-[1.2rem] border-2 transition-all duration-300 transform ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'} ${noneOfAbove ? 'border-amber-400 bg-amber-50/60 shadow-md scale-[1.01]' : 'border-dashed border-gray-300 bg-white hover:border-amber-300 hover:bg-amber-50/30 hover:shadow-sm'}`}
        >
          <div className="flex justify-between items-center">
            <span className={`font-bold text-base ${noneOfAbove ? 'text-amber-700' : 'text-gray-500'}`}>
              None of the above
            </span>
            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${noneOfAbove ? 'border-amber-400 bg-amber-400' : 'border-gray-300'}`}>
              {noneOfAbove && <CheckCircle2 size={16} className="text-white" />}
            </div>
          </div>
          {noneOfAbove && (
            <p className="text-xs text-amber-600 mt-2 font-medium">
              AI will generate a different set of questions for you.
            </p>
          )}
        </button>
      </div>

      <div style={{ transitionDelay: `${questions.length * 100 + 100}ms` }} className={`transition-all duration-700 transform ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <textarea
          className="w-full p-5 rounded-2xl border-2 border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all h-28 text-gray-800 resize-none text-base placeholder:text-gray-400 bg-white"
          placeholder="Any additional symptoms or triggers not listed? (Optional)" 
          value={additional} 
          onChange={e => setAdditional(e.target.value)}
        />
      </div>

      <button
        onClick={() => onSubmit?.({ selected, additional, noneOfAbove })} style={{ transitionDelay: `${questions.length * 100 + 200}ms` }}
        className={`w-full font-bold py-5 rounded-[1.5rem] shadow-xl transition-all transform active:scale-[0.98] text-lg ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'} ${noneOfAbove ? 'bg-amber-500 hover:bg-amber-600 shadow-amber-400/20 text-white' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-500/20 text-white'}`}
      >
        {noneOfAbove ? 'Get Different Questions' : 'Submit Additional Information'}
      </button>
    </div>
  );
};

const CARE_PATH_LABELS = {
  ER: 'Emergency Room',
  URGENT_CARE: 'Urgent Care',
  PRIMARY_CARE: 'Primary Care',
  SPECIALIST: 'Specialist',
};

// B. Triage Result Page (Stage 2)
export const RecommendationView = ({
  department = "Pending",
  carePath = "PRIMARY_CARE",
  confidence = 0.65,
  reasons = ["Analyzing your symptoms..."],
  selfCareOnly = false,
  onAgree,
  onDisagree,
  onBackHome,
  onRewriteSymptoms,
}) => (
  <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 max-w-2xl mx-auto pt-4">
    <div className="bg-[#f0f2f5] border-2 border-[#45b65f] rounded-[2rem] p-8 shadow-md relative overflow-hidden">
      <div className="absolute top-0 right-0 w-64 h-64 bg-white/50 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
      
      <div className="flex items-center gap-2 mb-6 text-[#45b65f] font-bold text-base relative z-10">
        <CheckCircle2 size={20} /><span>AI confidence reached {Math.round(confidence * 100)}%</span>
      </div>
      
      <h3 className="text-gray-500 text-sm mt-4 font-bold relative z-10 uppercase tracking-widest">Recommended Department</h3>
      <div className="flex items-center gap-6 mt-4 mb-8 relative z-10">
        <div className="p-5 bg-[#45b65f] rounded-[1.5rem] text-white shadow-xl shadow-green-500/20">
          <Stethoscope size={48} strokeWidth={1.5} />
        </div>
        <div>
          <h2 className="text-4xl font-black text-gray-800 tracking-tight">{department}</h2>
          <span className="text-[#45b65f] text-sm font-bold bg-[#45b65f]/15 px-3 py-1.5 rounded-lg inline-block mt-3">{CARE_PATH_LABELS[carePath] || carePath}</span>
        </div>
      </div>
      
      <div className="space-y-4 relative z-10 bg-black/5 p-6 rounded-2xl">
        <h4 className="text-xs font-black text-gray-400 mb-3 uppercase tracking-wider">AI Reasoning</h4>
        {reasons.map((r, i) => (
          <div key={i} className="flex gap-3 items-center text-base text-gray-700 font-medium leading-relaxed">
            <span className="w-2 h-2 bg-[#45b65f] rounded-full shrink-0"></span> {r}
          </div>
        ))}
      </div>
    </div>

    {!selfCareOnly ? (
      <div className="space-y-4 pt-4">
        <p className="text-center font-bold text-gray-800 text-base mb-4">Do you agree with this department recommendation?</p>
        <div className="flex gap-4">
          <button onClick={onDisagree} className="flex-1 py-5 rounded-[1.5rem] font-bold border-2 border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300 flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-base">
            <ThumbsDown size={20} /> Not accurate, re-answer
          </button>
          <button onClick={onAgree} className="flex-[1.5] py-5 rounded-[1.5rem] font-bold bg-[#45b65f] text-white shadow-xl shadow-green-600/20 hover:bg-[#3ca052] flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-base">
            <ThumbsUp size={20} /> Agree, find providers
          </button>
        </div>
      </div>
    ) : (
      <div className="space-y-4 pt-4">
        <p className="text-center font-bold text-gray-800 text-base mb-4">
          Based on current symptoms, home/self-care is reasonable. You can restart or rewrite symptoms.
        </p>
        <div className="flex gap-4">
          <button onClick={onRewriteSymptoms} className="flex-1 py-5 rounded-[1.5rem] font-bold border-2 border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300 flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-base">
            <RefreshCcw size={20} /> Rewrite symptoms
          </button>
          <button onClick={onBackHome} className="flex-[1.2] py-5 rounded-[1.5rem] font-bold bg-blue-600 text-white shadow-xl shadow-blue-600/20 hover:bg-blue-700 flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-base">
            <ChevronLeft size={20} /> Back to home
          </button>
        </div>
      </div>
    )}
  </div>
);

// C. Provider matching view (Stage 3)
export const ProvidersView = ({ providers = [], onSelectProvider, onCheckInsurance }) => {
  const displayProviders = providers.map((p) => ({
    id: p.provider_id,
    name: p.name,
    type: p.provider_type || 'Provider',
    address: p.address || '',
    distance: p.distance_km != null ? `${p.distance_km} km` : 'Distance unknown',
    nextSlot: p.next_available_slot || 'Please contact provider to confirm',
    mapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      p.address || p.name || ''
    )}`,
    raw: p
  }));

  return (
    <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500 max-w-3xl mx-auto pt-4">
      <div className="flex items-center justify-between px-2 mb-4">
        <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Matched providers near you</h2>
        <span className="text-xs text-blue-600 font-bold bg-blue-50 px-4 py-1.5 rounded-full border border-blue-100">
          {displayProviders.length} nearby
        </span>
      </div>

      {/* Wide list layout with space-y-4 */}
      <div className="space-y-5">
        {displayProviders.map((p, i) => (
          <div key={p.id} style={{ animationDelay: `${i * 100}ms` }} className="bg-white border border-gray-100 rounded-[1.5rem] p-6 hover:border-blue-300 hover:shadow-lg transition-all shadow-sm group animate-in fade-in slide-in-from-bottom-4">
            
            <div className="flex gap-5 mb-2">
              {/* Left icon */}
              <div className="p-4 bg-gray-50 rounded-2xl text-gray-400 group-hover:bg-blue-50 group-hover:text-blue-500 transition-colors shrink-0 h-fit">
                <Building2 size={28} />
              </div>
              
              {/* Right info column */}
              <div className="flex-1">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <h3 className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors text-xl leading-tight">{p.name}</h3>
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest bg-gray-50 px-3 py-1.5 rounded-lg w-fit shrink-0">{p.type}</span>
                </div>
                
                {/* Distance and time */}
                <div className="flex flex-wrap items-center text-sm text-gray-500 gap-8 font-medium mb-1">
                  <span className="flex items-center gap-2"><MapPin size={16} className="text-blue-400" /> Distance {p.distance}</span>
                  <span className="flex items-center gap-2"><Clock size={16} className="text-amber-400" /> Earliest slot:{p.nextSlot}</span>
                </div>
                <div className="mt-2 text-sm text-gray-500 flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
                  <span className="flex items-center gap-2 min-w-0">
                    <MapPin size={15} className="text-gray-400 shrink-0" />
                    <span className="truncate">{p.address || 'Address not provided'}</span>
                  </span>
                  <a
                    href={p.mapsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-blue-600 hover:text-blue-700 font-bold whitespace-nowrap shrink-0"
                  >
                    Open in Google Maps <ExternalLink size={14} />
                  </a>
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-4 mt-6 pt-5 border-t border-gray-50 sm:ml-[4.5rem]">
              <button 
                onClick={() => onCheckInsurance?.(p.raw)} 
                className="flex-1 py-3.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
              >
                <ShieldCheck size={18} /> Check Insurance
              </button>
              <button 
                onClick={() => onSelectProvider?.(p.raw)} 
                className="flex-[2] py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 active:scale-[0.98] shadow-md shadow-blue-500/20"
              >
                Book with Provider <ChevronRight size={18} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// D1. Insurance Query – Input Page
export const InsuranceView = ({ providerName, onQuery, initialPlan = '' }) => {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan || "Unknown / Self-pay");

  return (
    <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 max-w-2xl mx-auto pt-4">
      <div className="bg-indigo-50 border border-indigo-100 rounded-[2rem] p-8 shadow-sm relative overflow-hidden">
        <div className="absolute -right-10 -top-10 text-indigo-100 opacity-40"><ShieldCheck size={200} /></div>
        <div className="relative z-10">
          <div className="flex items-center gap-4 mb-6">
            <div className="p-3 bg-indigo-500 rounded-2xl text-white shadow-lg shadow-indigo-500/30"><ShieldCheck size={32} /></div>
            <h2 className="text-3xl font-black text-indigo-900">Select Your Insurance</h2>
          </div>
          
          {providerName && (
            <div className="bg-white/70 p-4 rounded-xl border border-indigo-100/50 mb-6 text-base text-indigo-800 font-medium flex items-center gap-3 shadow-sm">
              <Building2 size={20} className="text-indigo-500"/>
              <span className="truncate flex-1">Target Provider:<span className="font-bold text-indigo-900">{providerName}</span></span>
            </div>
          )}

          <p className="text-indigo-800 text-sm mb-8 leading-relaxed font-medium">
            Select your insurance plan. After you choose one, we search that insurer's network for the target provider and estimate costs.
          </p>

          <div className="space-y-4">
            <label className="block text-xs font-black text-indigo-400 uppercase tracking-widest">Insurance Plans</label>
            <div className="relative">
              <select 
                value={selectedPlan}
                onChange={(e) => setSelectedPlan(e.target.value)}
                className="w-full p-5 rounded-2xl border-2 border-indigo-200 bg-white text-base font-bold text-indigo-900 outline-none focus:ring-4 focus:ring-indigo-500/20 appearance-none cursor-pointer shadow-sm hover:border-indigo-300 transition-colors"
              >
                <option value="Aetna PPO">Aetna PPO</option>
                <option value="Blue Cross Blue Shield">Blue Cross Blue Shield</option>
                <option value="UnitedHealthcare">UnitedHealthcare</option>
                <option value="Medicare / Medicaid">Medicare / Medicaid</option>
                <option value="Unknown / Self-pay">Unknown / Self-pay</option>
              </select>
              <ChevronRight size={20} className="absolute right-5 top-1/2 -translate-y-1/2 text-indigo-400 rotate-90 pointer-events-none" />
            </div>
          </div>
        </div>
      </div>
      
      <button 
        onClick={() => onQuery(selectedPlan)} 
        className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-5 rounded-[1.5rem] shadow-xl shadow-indigo-600/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-lg"
      >
        <Search size={20} /> Check Insurance Coverage
      </button>
    </div>
  );
};

// D2. Insurance Query – Result Page
export const InsuranceResultView = ({ providerName, insurancePlan, result, onBackToProviders }) => {
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  const isFound = !!result?.in_network;
  const estimatedCost = result?.estimated_cost;
  const originalCost = result?.original_cost;
  const costBreakdown = result?.cost_breakdown || [];
  const currencySymbol = estimatedCost?.currency === 'USD' || originalCost?.currency === 'USD' ? '$' : '¥';

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 space-y-6 animate-in fade-in">
        <div className="relative">
          <div className="w-24 h-24 border-4 border-indigo-100 rounded-full"></div>
          <div className="w-24 h-24 border-4 border-indigo-600 rounded-full border-t-transparent animate-spin absolute top-0 left-0"></div>
          <ShieldCheck size={36} className="text-indigo-600 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
        </div>
        <p className="text-lg font-bold text-indigo-800 animate-pulse">Checking {insurancePlan} coverage...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 max-w-2xl mx-auto pt-4">
      
      {isFound ? (
        <div className="bg-green-50 border border-green-200 rounded-[2rem] p-8 shadow-sm">
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-green-500 rounded-full text-white shadow-lg shadow-green-500/30">
              <CheckCircle2 size={32} />
            </div>
            <div>
              <h2 className="text-2xl font-black text-green-900 leading-tight">This provider supports your insurance!</h2>
              <p className="text-sm font-bold text-green-700 mt-1">The selected plan appears in the provider network.</p>
            </div>
          </div>
          
          <div className="bg-white rounded-[1.5rem] p-6 border border-green-100 shadow-sm space-y-6">
            <div className="flex justify-between items-center pb-5 border-b border-gray-100 border-dashed">
              <span className="text-sm font-bold text-gray-400">Estimated baseline cost (self-pay)</span>
                <span className="text-xl font-bold text-gray-400 line-through decoration-2">
                  {originalCost ? `${currencySymbol} ${originalCost.min} - ${originalCost.max}` : `${currencySymbol} 180 - 420`}
                </span>
            </div>
            <div className="flex justify-between items-end">
              <div>
                <span className="block text-sm font-bold text-green-600 mb-1">With {insurancePlan} estimated out-of-pocket cost</span>
                <span className="text-xs text-gray-400">(includes consultation and standard tests)</span>
              </div>
                <span className="text-3xl font-black text-green-600">
                  {estimatedCost ? `${currencySymbol} ${estimatedCost.min} - ${estimatedCost.max}` : `${currencySymbol} 25 - 90`}
                </span>
            </div>

            {/* Cost breakdown detail (collapsible) */}
            <div className="pt-4 border-t border-gray-100">
              <button 
                onClick={() => setShowDetails(!showDetails)}
                className="flex items-center justify-between w-full text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
              >
                <span>View cost breakdown</span>
                <ChevronRight size={16} className={`transition-transform duration-300 ${showDetails ? 'rotate-90' : ''}`} />
              </button>
              
              {showDetails && (
                <div className="mt-4 p-4 bg-gray-50 rounded-xl space-y-3 text-xs text-gray-600 animate-in slide-in-from-top-2">
                  {costBreakdown.length > 0 ? costBreakdown.map((item, idx) => (
                    <div className="flex justify-between" key={idx}>
                      <span>{item.item}</span>
                      <span className="font-bold">{item.range}</span>
                    </div>
                  )) : (
                    <>
                      <div className="flex justify-between">
                        <span>Specialist consultation</span>
                        <span className="font-bold">$ 30</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Lab/tests (estimated)</span>
                        <span className="font-bold">$ 20 - 100</span>
                      </div>
                    </>
                  )}
                  <div className="pt-2 border-t border-gray-200 border-dashed flex justify-between text-green-600 font-bold">
                    <span>Coverage ratio</span>
                    <span>{result?.coverage_ratio || 'About 85% - 90%'}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 pt-5 border-t border-gray-100 flex items-start gap-3 bg-gray-50/50 p-4 rounded-xl">
              <Info size={16} className="text-indigo-400 shrink-0 mt-0.5" />
              <p className="text-xs text-gray-500 leading-relaxed font-medium">
                {result?.notice || 'Estimated by AI based on historical patterns. Final reimbursement depends on your deductible. Please'}
                <a href="#" className="text-indigo-600 hover:text-indigo-800 hover:underline inline-flex items-center gap-1 ml-1 font-bold">
                  verify with your insurance provider <ExternalLink size={12} />
                </a>
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-200 rounded-[2rem] p-8 shadow-sm">
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-gray-400 rounded-full text-white shadow-lg">
              <XCircle size={32} />
            </div>
            <div>
              <h2 className="text-2xl font-black text-gray-800 leading-tight">No matching insurance record found</h2>
              <p className="text-sm font-bold text-gray-500 mt-1">This provider may be out-of-network, or you selected self-pay.</p>
            </div>
          </div>
          
          <div className="bg-white rounded-[1.5rem] p-6 border border-gray-100 shadow-sm space-y-6">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <DollarSign size={20} className="text-gray-400" />
                <span className="text-base font-bold text-gray-600">Estimated self-pay cost</span>
              </div>
              <span className="text-2xl font-black text-gray-800">
                {originalCost ? `${currencySymbol} ${originalCost.min} - ${originalCost.max}` : `${currencySymbol} 180 - 420`}
              </span>
            </div>
            
            {/* Cost breakdown detail (collapsible) – self-pay version */}
            <div className="pt-4 border-t border-gray-100">
              <button 
                onClick={() => setShowDetails(!showDetails)}
                className="flex items-center justify-between w-full text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
              >
                <span>View cost breakdown</span>
                <ChevronRight size={16} className={`transition-transform duration-300 ${showDetails ? 'rotate-90' : ''}`} />
              </button>
              
              {showDetails && (
                <div className="mt-4 p-4 bg-gray-50 rounded-xl space-y-3 text-xs text-gray-600 animate-in slide-in-from-top-2">
                  <div className="flex justify-between">
                    <span>Specialist consultation (self-pay)</span>
                    <span className="font-bold">$ 80 - 150</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Lab/tests (self-pay)</span>
                    <span className="font-bold">$ 60 - 180</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Medication (self-pay)</span>
                    <span className="font-bold">$ 40 - 90</span>
                  </div>
                  <div className="pt-2 border-t border-gray-200 border-dashed flex justify-between text-gray-400 font-medium">
                    <span>Insurance coverage</span>
                    <span>None</span>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 pt-5 border-t border-gray-100 flex items-start gap-3 bg-gray-50/50 p-4 rounded-xl">
              <Info size={16} className="text-indigo-400 shrink-0 mt-0.5" />
              <p className="text-xs text-gray-500 leading-relaxed font-medium">
                If you think this is incorrect or need a detailed self-pay breakdown,
                <a href="#" className="text-indigo-600 hover:text-indigo-800 hover:underline inline-flex items-center gap-1 ml-1 font-bold">
                  check the hospital website insurance list <ExternalLink size={12} />
                </a>
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4 pt-4">
        <button 
          onClick={onBackToProviders} 
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-5 rounded-[1.5rem] shadow-xl shadow-blue-500/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-lg"
        >
          Back to provider list <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
};

// E. Booking Confirmation & Result Page (Stage 4)
export const BookingView = ({ provider, onSubmit }) => {
  const [fullName, setFullName] = useState('Sarah Miller');
  const [phone, setPhone] = useState('138-0000-0000');

  return (
  <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500 max-w-2xl mx-auto pt-4">
    <div className="bg-blue-50 rounded-[2rem] p-8 border border-blue-100/50 shadow-inner">
      <div className="flex items-center gap-4 mb-6">
        <div className="p-3 bg-blue-500 rounded-xl text-white shadow-md shadow-blue-500/30"><CalendarCheck size={28} /></div>
        <h2 className="text-2xl font-black text-blue-900">Final intent confirmation</h2>
      </div>
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-blue-100/50 flex flex-col gap-2">
        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Selected Provider</span>
        <p className="text-lg font-bold text-gray-900">{provider?.name || 'Selected medical provider'}</p>
        <div className="mt-2 flex items-center gap-2 text-sm font-bold text-blue-600 bg-blue-50/50 w-fit px-3 py-1.5 rounded-lg">
          <Clock size={16} /> Suggested visit time: {provider?.next_available_slot || provider?.nextSlot || 'Today 3:30 PM'}
        </div>
      </div>
    </div>

    <div className="bg-white p-8 rounded-[2rem] border border-gray-100 shadow-sm space-y-6">
      <h3 className="text-base font-bold text-gray-800 mb-2 flex items-center gap-2"><User size={20} className="text-blue-500"/> Patient Contact</h3>
      <div className="space-y-5">
        <div>
          <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Full Name</label>
          <input type="text" className="w-full p-4 rounded-xl border border-gray-200 outline-none focus:ring-2 focus:ring-blue-500/50 text-base font-medium bg-gray-50 focus:bg-white transition-colors" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Phone Number</label>
          <input type="tel" className="w-full p-4 rounded-xl border border-gray-200 outline-none focus:ring-2 focus:ring-blue-500/50 text-base font-medium bg-gray-50 focus:bg-white transition-colors" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
      </div>
    </div>

    <button onClick={() => onSubmit?.({ full_name: fullName, phone })} className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-5 rounded-[1.5rem] shadow-xl shadow-green-600/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98] text-lg">
      Submit booking intent <CheckCircle2 size={24} />
    </button>
  </div>
  );
};

// F. Booking Success Page
export const SummaryView = ({ instructions = [], onRestart }) => (
  <div className="text-center py-16 space-y-8 animate-in zoom-in-95 duration-500 max-w-2xl mx-auto">
    <div className="w-32 h-32 bg-green-50 text-green-500 rounded-full flex items-center justify-center mx-auto mb-8 shadow-inner border-[8px] border-green-100/50">
      <CheckCircle2 size={64} strokeWidth={2.5} />
    </div>
    <h2 className="text-3xl font-black text-gray-900 tracking-tight">Intent Submitted Successfully</h2>
    <div className="text-base text-gray-500 leading-relaxed max-w-md mx-auto">
      <p>Your AI triage report and booking intent were securely sent to the provider. Please review:</p>
      <ul className="mt-8 text-left space-y-5 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
        {(instructions.length > 0 ? instructions : [
          'Watch for SMS updates or call the clinic front desk to confirm the final timeslot.',
          'Bring your insurance card and a valid photo ID when visiting.'
        ]).map((line, idx) => (
          <li className="flex gap-4 text-gray-700 font-medium text-base items-start" key={idx}>
            <span className="w-7 h-7 bg-green-500 text-white rounded-full flex items-center justify-center text-sm font-bold shrink-0 shadow-sm">{idx + 1}</span>
            {line}
          </li>
        ))}
      </ul>
    </div>
    <div className="pt-8">
      <button onClick={onRestart} className="inline-flex items-center justify-center gap-2 px-8 py-4 text-blue-600 font-bold text-base bg-blue-50 rounded-2xl hover:bg-blue-100 transition-colors">
        <RefreshCcw size={18} /> Start a New Triage Session
      </button>
    </div>
  </div>
);

/**
 * ==========================================
 * 3. API Key Settings Modal
 * ==========================================
 */
const API_KEY_FIELDS = [
  { id: 'openai',    label: 'OpenAI API Key',      placeholder: 'sk-proj-...' },
  { id: 'googleMaps', label: 'Google Maps API Key', placeholder: 'AIzaSy...' },
  { id: 'gemini',    label: 'Gemini API Key',       placeholder: 'AIzaSy...' },
  { id: 'tavily',    label: 'Tavily API Key',       placeholder: 'tvly-...' },
];

const ApiKeyModal = ({ onClose }) => {
  const [values, setValues] = useState(() => getStoredApiKeys());
  const [visible, setVisible] = useState({});
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    saveApiKeys(values);
    setSaved(true);
    setTimeout(() => { setSaved(false); onClose(); }, 900);
  };

  const handleClear = () => {
    const empty = { openai: '', googleMaps: '', gemini: '', tavily: '' };
    setValues(empty);
    saveApiKeys(empty);
  };

  const anyFilled = Object.values(values).some(Boolean);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(15,23,42,0.55)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <KeyRound size={18} className="text-blue-600" />
            <h2 className="text-base font-black text-slate-800">API Key Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors rounded-full p-1 hover:bg-slate-100"
          >
            <XCircle size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          <p className="text-xs text-slate-500 leading-relaxed">
            Enter your own API keys to override the server defaults. Leave a field blank to keep using the server&apos;s configured key.
          </p>

          {API_KEY_FIELDS.map(({ id, label, placeholder }) => (
            <div key={id}>
              <label className="block text-xs font-bold text-slate-600 mb-1">{label}</label>
              <div className="flex items-center gap-2">
                <input
                  type={visible[id] ? 'text' : 'password'}
                  value={values[id]}
                  onChange={e => setValues(prev => ({ ...prev, [id]: e.target.value }))}
                  placeholder={placeholder}
                  className="flex-1 text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300 font-mono placeholder:font-sans placeholder:text-slate-400 bg-slate-50"
                  autoComplete="off"
                />
                <button
                  type="button"
                  onClick={() => setVisible(prev => ({ ...prev, [id]: !prev[id] }))}
                  className="text-slate-400 hover:text-slate-600 transition-colors p-1"
                  tabIndex={-1}
                >
                  {visible[id] ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 flex items-center justify-between gap-3">
          <button
            onClick={handleClear}
            disabled={!anyFilled}
            className="text-xs font-semibold text-rose-500 hover:text-rose-700 disabled:opacity-30 transition-colors"
          >
            Clear all
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-semibold text-slate-600 border border-slate-200 rounded-full hover:bg-slate-50 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className={`px-4 py-2 text-sm font-bold rounded-full transition ${
                saved
                  ? 'bg-green-500 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {saved ? 'Saved ✓' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * ==========================================
 * 4. Main App Component
 * ==========================================
 */
export default function App() {
  const [currentView, setCurrentView] = useState('PROFILE');
  const [sessionId, setSessionId] = useState('');
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedInsurancePlan, setSelectedInsurancePlan] = useState('');
  const [followUpQuestions, setFollowUpQuestions] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [providers, setProviders] = useState([]);
  const [insuranceResult, setInsuranceResult] = useState(null);
  const [summary, setSummary] = useState(null);
  const [triageConfidencePercent, setTriageConfidencePercent] = useState(65);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  // User profile + location collected on the Profile page
  const [userProfile, setUserProfile] = useState({
    age: 0,
    sex: '',
    insurancePlan: '',
    city: '',
    lat: null,
    lng: null,
  });

  const getBrowserLocation = async () => {
    if (!navigator.geolocation) {
      throw new Error('Browser geolocation is not supported. Please provide address, city, or ZIP code.');
    }
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          resolve({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
          });
        },
        () => {
          reject(new Error('Unable to get GPS location. Please enable location access or provide more location details.'));
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  };

  const loadRecommendation = async (sid = sessionId) => {
    const data = await getRecommendation(sid);
    setRecommendation(data);
    setTriageConfidencePercent(
      Math.max(
        1,
        Math.min(
          100,
          Math.round(
            typeof data.confidence_percent === 'number'
              ? data.confidence_percent
              : (typeof data.confidence === 'number' && data.confidence > 1
                  ? data.confidence
                  : (data.confidence || 0.65) * 100)
          )
        )
      )
    );
    // Only escalate to full ER alert when care path is ER AND risk is truly HIGH
    // (avoids false alarms for mild/moderate symptoms like low-severity chest discomfort)
    if (
      data.care_path === 'ER' &&
      data.risk_level === 'HIGH' &&
      (data.red_flags_detected || []).length > 0
    ) {
      setCurrentView('ESCALATED');
      return;
    }
    setCurrentView('TRIAGE_READY');
  };

  const loadProviders = async (sid = sessionId, rec = recommendation) => {
    // Read latest profile via ref to avoid stale closure
    let profile = userProfile;
    let lat = profile.lat;
    let lng = profile.lng;
    let city = profile.city || '';
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      try {
        const gps = await getBrowserLocation();
        lat = gps.lat;
        lng = gps.lng;
        setUserProfile((prev) => {
          city = prev.city || 'GPS location';
          return { ...prev, lat, lng, city };
        });
      } catch {
        // GPS failed — proceed with city-only search (lat/lng stay null)
      }
    }
    const data = await searchProviders({
      session_id: sid,
      care_path: rec?.care_path || 'URGENT_CARE',
      location: {
        city,
        lat: Number.isFinite(lat) ? lat : undefined,
        lng: Number.isFinite(lng) ? lng : undefined,
        radius_km: 10,
      },
    });
    setProviders(data.providers || []);
    setCurrentView('PROVIDER_MATCHED');
  };

  const loadSummary = async (sid = sessionId) => {
    const data = await getSummary(sid);
    setSummary(data);
  };

  const runWithGuard = async (fn) => {
    setErrorMessage('');
    setLoading(true);
    try {
      await fn();
    } catch (e) {
      setErrorMessage(e.message || 'Request failed. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleProfileNext = async ({ detailAddress, city, zipCode, age, sex, insurancePlan }) => {
    await runWithGuard(async () => {
      const parts = [detailAddress, city, zipCode].map((x) => (x || '').trim()).filter(Boolean);
      const query = parts.join(', ');
      let geocoded = null;
      try {
        geocoded = await geocodeLocation({ query });
      } catch (_) {
        geocoded = null;
      }

      if (!geocoded) {
        // Geocode failed — try GPS as fallback, but don't block if GPS also fails
        try {
          const gps = await getBrowserLocation();
          setUserProfile({
            city: city || zipCode || 'GPS location',
            age,
            sex,
            insurancePlan,
            lat: gps.lat,
            lng: gps.lng,
          });
        } catch {
          // Both geocode and GPS failed — proceed with text-only location
          setUserProfile({
            city: city || zipCode || '',
            age,
            sex,
            insurancePlan,
            lat: null,
            lng: null,
          });
        }
        setCurrentView('INTAKE');
        return;
      }

      setUserProfile({
        city: city || geocoded.normalized_address || zipCode || 'GPS location',
        age,
        sex,
        insurancePlan,
        lat: geocoded.lat,
        lng: geocoded.lng,
      });
      setCurrentView('INTAKE');
    });
  };

  const handleIntakeSubmit = async ({ complaint, severity }) => {
    await runWithGuard(async () => {
      const response = await createSession({
        user_profile: {
          age: userProfile.age || 0,
          sex: userProfile.sex || 'unknown',
          city: userProfile.city || '',
          insurance_plan: userProfile.insurancePlan || 'Unknown'
        },
        symptom_input: {
          chief_complaint: complaint,
          duration_hours: 0,
          severity_0_10: severity,
          free_text: complaint
        },
        consent: {
          hipaa_ack: true,
          ai_guidance_ack: true
        }
      });
      setSessionId(response.session_id);
      setSummary({
        symptom_input: {
          chief_complaint: complaint,
          severity_0_10: severity
        }
      });
      setTriageConfidencePercent(
        Math.max(
          1,
          Math.min(
            100,
            Math.round(
              typeof response.confidence_percent === 'number'
                ? response.confidence_percent
                : (typeof response.confidence === 'number' && response.confidence > 1
                    ? response.confidence
                    : (response.confidence || 0.65) * 100)
            )
          )
        )
      );
      const normalizedQuestions = (response.questions || []).map((q) => ({
        id: q.question_id,
        text: q.label
      }));
      setFollowUpQuestions(normalizedQuestions);
      if ((response.status || 'FOLLOW_UP') === 'TRIAGE_READY') {
        await loadRecommendation(response.session_id);
      } else {
        setCurrentView('FOLLOW_UP');
      }
    });
  };

  const handleFollowUpSubmit = async ({ selected, additional, noneOfAbove = false }) => {
    if (!sessionId) return;
    await runWithGuard(async () => {
      const allAnswers = followUpQuestions.map((q) => ({
        question_id: q.id,
        value: selected.includes(q.id)
      }));
      const response = await submitAnswers(sessionId, {
        answers: allAnswers,
        additional_note: additional,
        none_of_above: noneOfAbove,
      });
      setTriageConfidencePercent(
        Math.max(
          1,
          Math.min(
            100,
            Math.round(
              typeof response.confidence_percent === 'number'
                ? response.confidence_percent
                : (typeof response.confidence === 'number' && response.confidence > 1
                    ? response.confidence
                    : (response.confidence || 0.65) * 100)
            )
          )
        )
      );
      if (response.status === 'FOLLOW_UP') {
        const normalizedQuestions = (response.questions || []).map((q) => ({
          id: q.question_id,
          text: q.label
        }));
        setFollowUpQuestions(normalizedQuestions);
        setCurrentView('FOLLOW_UP');
        return;
      }
      await loadRecommendation(sessionId);
    });
  };

  const handleAgreeRecommendation = async () => {
    if (!sessionId) return;
    const selfCareOnly = recommendation?.department === 'Primary Care'
      && recommendation?.care_path === 'PRIMARY_CARE'
      && recommendation?.visit_needed === false;
    if (selfCareOnly) {
      setCurrentView('PROFILE');
      return;
    }
    // Capture current values to avoid stale closure issues
    const currentSessionId = sessionId;
    const currentRecommendation = recommendation;
    await runWithGuard(async () => {
      const response = await sendRecommendationFeedback(currentSessionId, {
        decision: 'AGREE',
        comment: ''
      });
      if (response.next_status === 'PROVIDER_MATCHED') {
        await loadProviders(currentSessionId, currentRecommendation);
      }
    });
  };

  const handleDisagreeRecommendation = async () => {
    if (!sessionId) return;
    await runWithGuard(async () => {
      const response = await sendRecommendationFeedback(sessionId, {
        decision: 'DISAGREE',
        comment: 'User believes symptom details are incomplete'
      });
      setCurrentView(response.next_status || 'FOLLOW_UP');
    });
  };

  const handleRewriteSymptoms = () => {
    setCurrentView('INTAKE');
    setRecommendation(null);
    setFollowUpQuestions([]);
    setErrorMessage('');
  };

  const handleBack = () => {
    switch(currentView) {
      case 'INTAKE': setCurrentView('PROFILE'); break;
      case 'FOLLOW_UP': setCurrentView('INTAKE'); break;
      case 'TRIAGE_READY': setCurrentView('FOLLOW_UP'); break;
      case 'PROVIDER_MATCHED': setCurrentView('TRIAGE_READY'); break;
      case 'INSURANCE': setCurrentView('PROVIDER_MATCHED'); break;
      case 'INSURANCE_RESULT': setCurrentView('INSURANCE'); break;
      case 'BOOKING': setCurrentView('PROVIDER_MATCHED'); break;
      case 'COMPLETED': setCurrentView('BOOKING'); break;
      default: break;
    }
  };

  const handleInsuranceQuery = async (planName) => {
    setSelectedInsurancePlan(planName);
    if (!sessionId || !selectedProvider) return;
    await runWithGuard(async () => {
      const result = await checkInsurance({
        session_id: sessionId,
        provider_id: selectedProvider.provider_id,
        insurance_plan: planName
      });
      setInsuranceResult(result);
      setCurrentView('INSURANCE_RESULT');
    });
  };

  const handleBookingSubmit = async (patientContact) => {
    if (!sessionId || !selectedProvider) return;
    await runWithGuard(async () => {
      const booking = await createBookingIntent({
        session_id: sessionId,
        provider_id: selectedProvider.provider_id,
        preferred_time: selectedProvider.next_available_slot || new Date(Date.now() + 2 * 3600000).toISOString(),
        patient_contact: patientContact,
        confirmation: {
          user_confirmed_details: true,
          ai_not_diagnosis_ack: true
        }
      });
      // Save booking summary to localStorage so it appears on home page
      const localRecord = {
        booking_intent_id: booking.booking_intent_id,
        provider_name: selectedProvider.name || selectedProvider.provider_name || 'Provider',
        provider_address: selectedProvider.address || '',
        department: recommendation?.department || '',
        care_path: recommendation?.care_path || '',
        patient_name: patientContact.full_name,
        phone: patientContact.phone,
        preferred_time: selectedProvider.next_available_slot || new Date(Date.now() + 2 * 3600000).toISOString(),
        booked_at: new Date().toISOString(),
        status: 'CONFIRMED',
      };
      try {
        const existing = JSON.parse(localStorage.getItem('healthcare_bookings') || '[]');
        localStorage.setItem('healthcare_bookings', JSON.stringify([localRecord, ...existing]));
      } catch (_) {}
      await loadSummary(sessionId);
      setSummary((prev) => ({ ...(prev || {}), instructions: booking.instructions || [] }));
      setCurrentView('COMPLETED');
    });
  };

  const resetAll = () => {
    setCurrentView('PROFILE');
    setSessionId('');
    setSelectedProvider(null);
    setSelectedInsurancePlan('');
    setFollowUpQuestions([]);
    setRecommendation(null);
    setProviders([]);
    setInsuranceResult(null);
    setSummary(null);
    setErrorMessage('');
    setUserProfile({ age: 0, sex: '', insurancePlan: '', city: '', lat: null, lng: null });
  };

  return (
    <div className="min-h-screen bg-[#f3f4f6] p-4 md:p-8 flex flex-col items-center font-sans">

      {showApiKeyModal && <ApiKeyModal onClose={() => setShowApiKeyModal(false)} />}

      {errorMessage && (
        <div className="w-full max-w-5xl mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {errorMessage}
        </div>
      )}

      {/* ================= Main Container ================= */}
      <div className="w-full max-w-4xl bg-white rounded-[2rem] shadow-2xl overflow-hidden flex flex-col border border-slate-200 min-h-[750px]">

        {/* Main interaction area */}
        <div className="flex-1 flex flex-col relative bg-white">
          {loading && <AIAnalyzingOverlay currentView={currentView} />}
          
          {/* Header & progress bar */}
          <div className="px-10 pt-5 pb-6 border-b border-gray-100 bg-white z-10 shadow-sm">
            {/* Top toolbar: API Keys button */}
            <div className="flex justify-end mb-5">
              <button
                onClick={() => setShowApiKeyModal(true)}
                title="API Key Settings"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-400 border border-slate-200 rounded-full hover:bg-slate-50 hover:text-blue-600 hover:border-blue-200 transition-colors"
              >
                <Settings size={12} />
                API Keys
              </button>
            </div>
            <ProgressBar currentStep={currentView} />
          </div>

          {/* Main content flow */}
          <div className="flex-1 px-8 py-8 overflow-y-auto custom-scrollbar relative bg-[#fcfdfd]">
            {currentView !== 'PROFILE' && currentView !== 'INTAKE' && currentView !== 'COMPLETED' && (
              <div className="mb-6 max-w-2xl mx-auto">
                <button onClick={handleBack} className="inline-flex items-center gap-1 text-[14px] text-slate-500 hover:text-blue-600 font-bold transition-colors group px-4 py-2 bg-white border border-gray-200 rounded-full shadow-sm hover:shadow">
                  <ChevronLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
                  Back
                </button>
              </div>
            )}

            {currentView === 'PROFILE' && <ProfileView onNext={handleProfileNext} />}
            {currentView === 'INTAKE' && <IntakeView onSubmit={handleIntakeSubmit} />}
            {currentView === 'FOLLOW_UP' && <FollowUpView questions={followUpQuestions} confidence={triageConfidencePercent / 100} onSubmit={handleFollowUpSubmit} />}
            {currentView === 'TRIAGE_READY' && (
              <RecommendationView
                department={recommendation?.department || 'Pending'}
                carePath={recommendation?.care_path || 'PRIMARY_CARE'}
                confidence={triageConfidencePercent / 100}
                reasons={recommendation?.reasons || ['Analyzing your symptoms...']}
                selfCareOnly={
                  recommendation?.department === 'Primary Care'
                  && recommendation?.care_path === 'PRIMARY_CARE'
                  && recommendation?.visit_needed === false
                }
                onAgree={handleAgreeRecommendation}
                onDisagree={handleDisagreeRecommendation}
                onBackHome={resetAll}
                onRewriteSymptoms={handleRewriteSymptoms}
              />
            )}
            {currentView === 'PROVIDER_MATCHED' && <ProvidersView providers={providers} onSelectProvider={(provider) => { setSelectedProvider(provider); setCurrentView('BOOKING'); }} onCheckInsurance={(provider) => { setSelectedProvider(provider); setCurrentView('INSURANCE'); }} />}
            {currentView === 'INSURANCE' && <InsuranceView providerName={selectedProvider?.name} onQuery={handleInsuranceQuery} initialPlan={userProfile.insurancePlan} />}
            {currentView === 'INSURANCE_RESULT' && <InsuranceResultView providerName={selectedProvider?.name} insurancePlan={selectedInsurancePlan} result={insuranceResult} onBackToProviders={() => setCurrentView('PROVIDER_MATCHED')} />}
            {currentView === 'BOOKING' && <BookingView provider={selectedProvider} onSubmit={handleBookingSubmit} />}
            {currentView === 'COMPLETED' && <SummaryView instructions={summary?.instructions || []} onRestart={resetAll} />}
            {currentView === 'ESCALATED' && (
              <div className="max-w-2xl mx-auto space-y-4">
                <div className="rounded-[1.5rem] border border-red-200 bg-red-50 p-6">
                  <h2 className="text-xl font-black text-red-700">High-risk symptoms detected</h2>
                  <p className="mt-2 text-sm font-semibold text-red-600">Please go to the emergency room now or call 911.</p>
                  {(recommendation?.red_flags_detected || []).length > 0 && (
                    <ul className="mt-3 list-disc list-inside text-sm text-red-700 space-y-1">
                      {recommendation.red_flags_detected.map((flag, i) => (
                        <li key={i}>{flag}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <p className="text-xs text-slate-400 text-center px-4">
                  This is AI navigation guidance, not a medical diagnosis. If you believe this is a false alert, please go back and clarify your symptoms.
                </p>
                <div className="text-center">
                  <button
                    onClick={() => setCurrentView('INTAKE')}
                    className="px-5 py-2 text-sm font-semibold text-slate-600 border border-slate-300 rounded-full hover:bg-slate-100 transition"
                  >
                    Re-describe my symptoms
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
