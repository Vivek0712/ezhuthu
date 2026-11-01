import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { Busy, ErrorNote } from '../components/Feedback';

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const { completeSignIn } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const code = params.get('code');
    const state = params.get('state');
    if (!code || !state) {
      setError(new Error(params.get('error_description') ?? 'missing code'));
      return;
    }
    completeSignIn(code, state).then((to) => navigate(to, { replace: true }), setError);
  }, [params, completeSignIn, navigate]);

  return error != null ? <ErrorNote error={error} /> : <Busy />;
}
