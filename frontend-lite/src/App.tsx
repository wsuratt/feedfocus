import { useState } from 'react';
import { Sparkles, CheckCircle, Clock, Mail, ArrowRight } from 'lucide-react';

type Status = 'idle' | 'loading' | 'immediate' | 'queued';

export default function App() {
  const [formData, setFormData] = useState({ email: '', topic: '' });
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');

    try {
      const response = await fetch('/api/lite/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        setStatus(data.status);
        setMessage(data.message);
      } else {
        throw new Error(data.detail || 'Submission failed');
      }
    } catch (error) {
      console.error('Submission failed:', error);
      setStatus('idle');
      alert('Something went wrong. Please try again.');
    }
  };

  if (status === 'immediate' || status === 'queued') {
    return <SuccessScreen status={status} email={formData.email} message={message} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo/Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-600 rounded-2xl mb-4 shadow-lg">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            FeedFocus
          </h1>
          <p className="text-lg text-gray-600">
            Curated insights delivered to your inbox
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Get Started
            </h2>
            <p className="text-gray-600">
              Enter any topic and we'll send you the best insights
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Topic Input */}
            <div>
              <label htmlFor="topic" className="block text-sm font-medium text-gray-700 mb-2">
                What topic interests you?
              </label>
              <input
                id="topic"
                type="text"
                value={formData.topic}
                onChange={(e) => setFormData({...formData, topic: e.target.value})}
                placeholder="e.g. AI agents, productivity, startups"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition text-base"
                required
                disabled={status === 'loading'}
              />
            </div>

            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Your email address
              </label>
              <input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                placeholder="you@example.com"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition text-base"
                required
                disabled={status === 'loading'}
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={status === 'loading'}
              className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-base transition flex items-center justify-center gap-2 shadow-lg hover:shadow-xl"
            >
              {status === 'loading' ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <span>Get Insights</span>
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </form>

          {/* Trust Indicators */}
          <div className="mt-6 pt-6 border-t border-gray-100">
            <div className="flex items-center justify-center gap-6 text-sm text-gray-500">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4" />
                <span>Free forever</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                <span>No spam</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          Get 5-10 curated insights delivered instantly or within 2 hours
        </p>
      </div>
    </div>
  );
}

function SuccessScreen({ status, email, message }: { status: 'immediate' | 'queued', email: string, message: string }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center border border-gray-100">
        {status === 'immediate' ? (
          <>
            <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-6">
              <CheckCircle className="w-10 h-10 text-green-600" />
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-3">Check Your Email!</h2>
            <p className="text-gray-600 text-lg mb-2">
              {message}
            </p>
            <p className="text-sm text-gray-500 mb-6">
              Sent to <strong>{email}</strong>
            </p>
          </>
        ) : (
          <>
            <div className="inline-flex items-center justify-center w-20 h-20 bg-indigo-100 rounded-full mb-6">
              <Clock className="w-10 h-10 text-indigo-600" />
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-3">We're On It!</h2>
            <p className="text-gray-600 text-lg mb-2">
              {message}
            </p>
            <p className="text-sm text-gray-500 mb-6">
              We'll send them to <strong>{email}</strong>
            </p>
          </>
        )}

        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-6">
          <p className="text-sm text-gray-700">
            <strong>Want weekly updates?</strong>
            <br />
            Just reply to the email when you receive it
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="text-indigo-600 hover:text-indigo-700 font-medium text-sm"
        >
          Submit another topic →
        </button>
      </div>
    </div>
  );
}
