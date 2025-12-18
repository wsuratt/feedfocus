import { useState } from 'react';
import { CheckCircle, Clock, ArrowRight } from 'lucide-react';

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
    <div className="min-h-screen flex items-center justify-center bg-white px-4 py-12">
      <div className="w-full max-w-md">
        <h1 className="text-6xl font-bold mb-12 text-center">The internet, refocused</h1>

        <div className="max-w-xs mx-auto">
          <h2 className="text-3xl font-bold mb-8">Get curated insights.</h2>

            <form onSubmit={handleSubmit} className="space-y-4">
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
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                  disabled={status === 'loading'}
                />
              </div>

              {/* Email Input */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                  Your email
                </label>
                <input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                  disabled={status === 'loading'}
                />
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full py-3 px-4 bg-black text-white rounded-full font-bold hover:bg-gray-900 transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {status === 'loading' ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Sending...</span>
                  </>
                ) : (
                  <>
                    <span>Get Insights</span>
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </form>

          <p className="text-xs text-gray-600 mt-6 text-center">
            We'll send 5-10 curated insights to your inbox.
          </p>
        </div>
      </div>
    </div>
  );
}

function SuccessScreen({ status, email, message }: { status: 'immediate' | 'queued', email: string, message: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md text-center">
        {status === 'immediate' ? (
          <>
            <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-6">
              <CheckCircle className="w-10 h-10 text-green-600" />
            </div>
            <h1 className="text-5xl font-bold mb-4">Check your email!</h1>
            <p className="text-xl text-gray-600 mb-2">
              {message}
            </p>
            <p className="text-sm text-gray-500 mb-8">
              Sent to <strong>{email}</strong>
            </p>
          </>
        ) : (
          <>
            <div className="inline-flex items-center justify-center w-20 h-20 bg-blue-100 rounded-full mb-6">
              <Clock className="w-10 h-10 text-blue-600" />
            </div>
            <h1 className="text-5xl font-bold mb-4">We're on it!</h1>
            <p className="text-xl text-gray-600 mb-2">
              {message}
            </p>
            <p className="text-sm text-gray-500 mb-8">
              We'll send them to <strong>{email}</strong>
            </p>
          </>
        )}

        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 mb-8 max-w-sm mx-auto">
          <p className="text-sm text-gray-700">
            <strong>Want weekly updates?</strong>
            <br />
            Click the subscribe button in the email
          </p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          Submit another topic →
        </button>
      </div>
    </div>
  );
}
