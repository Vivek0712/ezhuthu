import { useEffect, useRef, useState, type RefObject } from 'react';

/**
 * [ref, inView]: true while the element is on screen (or, with `once`, from the first time it is). Animations on
 * /how-it-works start only when their figure scrolls into view. Without IntersectionObserver (tests, old browsers)
 * it is always true, so everything renders in its finished state.
 */
export function useInView<T extends Element>(once = false, rootMargin = '0px 0px -10% 0px'): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(() => typeof window === 'undefined' || typeof window.IntersectionObserver !== 'function');
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof window.IntersectionObserver !== 'function') return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e) return;
        if (e.isIntersecting) {
          setInView(true);
          if (once) io.disconnect();
        } else if (!once) setInView(false);
      },
      { rootMargin, threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [once, rootMargin]);
  return [ref, inView];
}
