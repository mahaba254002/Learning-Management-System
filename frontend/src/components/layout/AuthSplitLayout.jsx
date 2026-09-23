import { motion, useReducedMotion } from "framer-motion";
import "./AuthSplitLayout.css";

const panelVariants = {
  hidden: { opacity: 0, y: -8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

const headingVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, delay: 0.15, ease: "easeOut" } },
};

const formVariants = {
  hidden: { opacity: 0, x: 16 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.6, delay: 0.25, ease: "easeOut" } },
};

/**
 * Shared two-column shell for the student auth pages (login, forgot
 * password, reset password, change password). Left panel carries brand +
 * heading + decorative motion; right panel is a plain card that hosts
 * whatever form the page passes as children.
 *
 * Deliberately student-only for now — no link back to the staff login,
 * since the two portals are meant to be fully separate doors.
 */
export default function AuthSplitLayout({ heading, subheading, children }) {
  const prefersReducedMotion = useReducedMotion();

  // With reduced motion, entrance animations still run (they're brief,
  // one-shot, and don't loop) but the continuous floating shapes are
  // skipped entirely rather than just slowed down — an infinite loop is
  // exactly the kind of motion prefers-reduced-motion is meant to avoid.
  const shapeFloat = (duration, delay = 0) =>
    prefersReducedMotion
      ? {}
      : {
          animate: { y: [0, -14, 0] },
          transition: { duration, delay, repeat: Infinity, ease: "easeInOut" },
        };

  return (
    <div className="auth-split">
      <div className="auth-split__panel">
        <motion.div
          className="auth-split__brand"
          initial="hidden"
          animate="visible"
          variants={panelVariants}
        >
          <span className="auth-split__logo" aria-hidden="true" />
          <span>Rollcall</span>
        </motion.div>

        <motion.div
          className="auth-split__heading"
          initial="hidden"
          animate="visible"
          variants={headingVariants}
        >
          <h1>{heading}</h1>
          {subheading && <p>{subheading}</p>}
        </motion.div>

        <div className="auth-split__shapes" aria-hidden="true">
          <motion.span
            className="auth-split__shape auth-split__shape--circle-lg"
            {...shapeFloat(4.5)}
          />
          <motion.span
            className="auth-split__shape auth-split__shape--circle-sm"
            {...shapeFloat(5.2, 0.4)}
          />
          <motion.span
            className="auth-split__shape auth-split__shape--square"
            {...shapeFloat(5.8, 0.8)}
          />
        </div>
      </div>

      <div className="auth-split__form-side">
        <motion.div
          className="auth-split__form-area"
          initial="hidden"
          animate="visible"
          variants={formVariants}
        >
          {children}
        </motion.div>
      </div>
    </div>
  );
}