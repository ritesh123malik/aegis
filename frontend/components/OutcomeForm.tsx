import { useState } from "react";
import { submitOutcome, OutcomeSubmissionResult } from "../lib/api";
import { CheckCircle2, AlertOctagon, Send, Loader } from "lucide-react";

interface OutcomeFormProps {
  eventId: string;
  onSubmitted: (result: OutcomeSubmissionResult) => void;
}

export default function OutcomeForm({ eventId, onSubmitted }: OutcomeFormProps) {
  const [actualDuration, setActualDuration] = useState<string>("");
  const [actualDisruption, setActualDisruption] = useState<string>("Medium");
  const [actualOfficers, setActualOfficers] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [loggedBy, setLoggedBy] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Validation states
  const [validationErrors, setValidationErrors] = useState<{
    actualDuration?: string;
    actualOfficers?: string;
    loggedBy?: string;
  }>({});

  const validate = () => {
    const errors: typeof validationErrors = {};
    
    const durationNum = parseFloat(actualDuration);
    if (isNaN(durationNum) || durationNum <= 0) {
      errors.actualDuration = "Duration must be a positive number.";
    }

    const officersNum = parseInt(actualOfficers, 10);
    if (isNaN(officersNum) || officersNum < 0 || !Number.isInteger(Number(actualOfficers))) {
      errors.actualOfficers = "Officers deployed must be a non-negative integer.";
    }

    if (!loggedBy.trim()) {
      errors.loggedBy = "Logged by / operator identifier is required.";
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSuccess(false);

    if (!validate()) {
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        actual_duration_min: parseFloat(actualDuration),
        actual_disruption_class: actualDisruption,
        actual_officers_deployed: parseInt(actualOfficers, 10),
        notes: notes.trim() || undefined,
        logged_by: loggedBy.trim()
      };

      const result = await submitOutcome(eventId, payload);
      setSuccess(true);
      
      // Keep success message visible briefly before triggering callback to visual feedback
      setTimeout(() => {
        onSubmitted(result);
        // Reset form except operator name
        setActualDuration("");
        setActualOfficers("");
        setNotes("");
        setSuccess(false);
      }, 2500);

    } catch (err: any) {
      setSubmitError(err.message || "Failed to submit outcome record.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 font-sans text-slate-100 shadow-xl flex flex-col gap-4">
      <h2 className="text-sm font-black tracking-wider border-b border-slate-700 pb-2 text-slate-400 uppercase">
        LOG ACTUAL OUTCOME (RECALIBRATION LOOP)
      </h2>

      {success ? (
        <div className="flex flex-col items-center justify-center py-8 px-4 bg-emerald-950/80 border-2 border-emerald-500 rounded text-center shadow-lg animate-pulse">
          <CheckCircle2 className="w-12 h-12 text-emerald-400 mb-3" />
          <span className="font-extrabold text-emerald-400 uppercase tracking-wider text-sm">
            Outcome Logged Successfully
          </span>
          <span className="text-xs text-emerald-250 mt-1 leading-relaxed">
            Recalibration bias loop triggered. Chart updating...
          </span>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4.5">
          {submitError && (
            <div className="flex gap-2.5 bg-red-950 border border-red-800 p-3 rounded text-red-200 shadow-md">
              <AlertOctagon className="w-5 h-5 flex-shrink-0 text-red-500" />
              <div className="text-[11px] leading-relaxed">
                <span className="font-bold text-red-400 block mb-0.5 uppercase">SUBMISSION FAILED</span>
                {submitError}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {/* Duration Input */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                ACTUAL DURATION (MIN)
              </label>
              <input
                type="number"
                step="any"
                value={actualDuration}
                onChange={(e) => setActualDuration(e.target.value)}
                placeholder="e.g. 120"
                className={`bg-slate-900 border ${
                  validationErrors.actualDuration ? "border-red-500" : "border-slate-750"
                } rounded p-2 text-xs text-white focus:outline-none focus:border-accentBlue`}
              />
              {validationErrors.actualDuration && (
                <span className="text-[9px] text-red-400 font-semibold">{validationErrors.actualDuration}</span>
              )}
            </div>

            {/* Officers Input */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                OFFICERS DEPLOYED
              </label>
              <input
                type="number"
                value={actualOfficers}
                onChange={(e) => setActualOfficers(e.target.value)}
                placeholder="e.g. 8"
                className={`bg-slate-900 border ${
                  validationErrors.actualOfficers ? "border-red-500" : "border-slate-750"
                } rounded p-2 text-xs text-white focus:outline-none focus:border-accentBlue`}
              />
              {validationErrors.actualOfficers && (
                <span className="text-[9px] text-red-400 font-semibold">{validationErrors.actualOfficers}</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Disruption Class Select */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                ACTUAL DISRUPTION CLASS
              </label>
              <select
                value={actualDisruption}
                onChange={(e) => setActualDisruption(e.target.value)}
                className="bg-slate-900 border border-slate-750 rounded p-2 text-xs text-white focus:outline-none focus:border-accentBlue"
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
                <option value="Critical">Critical</option>
              </select>
            </div>

            {/* Logged By Input */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                OPERATOR ID / LOGGED BY
              </label>
              <input
                type="text"
                value={loggedBy}
                onChange={(e) => setLoggedBy(e.target.value)}
                placeholder="e.g. Inspector R. Gowda"
                className={`bg-slate-900 border ${
                  validationErrors.loggedBy ? "border-red-500" : "border-slate-750"
                } rounded p-2 text-xs text-white focus:outline-none focus:border-accentBlue`}
              />
              {validationErrors.loggedBy && (
                <span className="text-[9px] text-red-400 font-semibold">{validationErrors.loggedBy}</span>
              )}
            </div>
          </div>

          {/* Notes Textarea */}
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              FIELD OBSERVATIONS / NOTES
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Provide context regarding actual delays, water levels, blockages, etc."
              className="bg-slate-900 border border-slate-750 rounded p-2 text-xs text-white focus:outline-none focus:border-accentBlue resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-accentBlue hover:bg-blue-600 active:bg-blue-700 disabled:bg-slate-700 text-white font-bold text-xs py-2.5 px-4 rounded transition-all duration-150 flex items-center justify-center gap-2 uppercase shadow-lg shadow-blue-500/10"
          >
            {submitting ? (
              <>
                <Loader className="w-3.5 h-3.5 animate-spin" /> Submitting...
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" /> Log Outcome &amp; Recalibrate
              </>
            )}
          </button>
        </form>
      )}
    </div>
  );
}
