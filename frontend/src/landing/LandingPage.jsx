/**
 * @file LandingPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useEffect, useRef, useState, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useScroll, useTransform, useInView } from 'framer-motion'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import {
  HiOutlineSparkles,
  HiOutlineBoltSlash,
  HiOutlineShieldCheck,
  HiOutlineCpuChip,
  HiOutlineDocumentMagnifyingGlass,
  HiOutlineLockClosed,
  HiOutlineArrowRight,
  HiOutlineArrowUpRight,
} from 'react-icons/hi2'
import Loader from './Loader'
import MagneticCursor from './MagneticCursor'
import Scene3D from './Scene3D'
import './LandingPage.css'

gsap.registerPlugin(ScrollTrigger)

// ── Animated text reveal ─────────────
function RevealText({ children, delay = 0, className = '' }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <div ref={ref} className={`reveal-text ${className}`}>
      <motion.div
        initial={{ y: '110%', rotateX: -80 }}
        animate={isInView ? { y: '0%', rotateX: 0 } : {}}
        transition={{
          duration: 1,
          delay,
          ease: [0.16, 1, 0.3, 1],
        }}
        style={{ transformOrigin: 'bottom', perspective: 500 }}
      >
        {children}
      </motion.div>
    </div>
  )
}

// ── Parallax wrapper ─────────────────
function ParallaxSection({ children, speed = 0.5, className = '' }) {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })
  const y = useTransform(scrollYProgress, [0, 1], [100 * speed, -100 * speed])

  return (
    <motion.div ref={ref} style={{ y }} className={className}>
      {children}
    </motion.div>
  )
}

// ── Feature card ─────────────────────
function FeatureCard({ icon: Icon, title, description, index }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <motion.div
      ref={ref}
      className="feature-card"
      initial={{ opacity: 0, y: 60, scale: 0.95 }}
      animate={isInView ? { opacity: 1, y: 0, scale: 1 } : {}}
      transition={{
        duration: 0.8,
        delay: index * 0.12,
        ease: [0.16, 1, 0.3, 1],
      }}
      whileHover={{ y: -8, transition: { duration: 0.3 } }}
      data-magnetic
    >
      <div className="feature-card__icon-wrap">
        <Icon className="feature-card__icon" />
        <div className="feature-card__icon-glow" />
      </div>
      <h3 className="feature-card__title">{title}</h3>
      <p className="feature-card__desc">{description}</p>
      <div className="feature-card__shine" />
    </motion.div>
  )
}

// ── Stat counter ─────────────────────
function StatCounter({ value, suffix = '', label, index }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true })
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (!isInView) return
    const obj = { val: 0 }
    gsap.to(obj, {
      val: value,
      duration: 2,
      delay: index * 0.2,
      ease: 'power2.out',
      onUpdate: () => setDisplay(Math.floor(obj.val)),
    })
  }, [isInView, value, index])

  return (
    <motion.div
      ref={ref}
      className="stat"
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.15, duration: 0.6 }}
    >
      <span className="stat__value">
        {display}
        {suffix}
      </span>
      <span className="stat__label">{label}</span>
    </motion.div>
  )
}

// ── Marquee ──────────────────────────
function Marquee() {
  const items = [
    'AI-POWERED', 'KNOWLEDGE BASE', 'ROLE-BASED ACCESS', 'REAL-TIME',
    'SEMANTIC SEARCH', 'DOCUMENT INGESTION', 'ENTERPRISE READY',
    'VECTOR SEARCH', 'RAG PIPELINE', 'SECURE',
  ]

  return (
    <div className="marquee">
      <motion.div
        className="marquee__track"
        animate={{ x: ['0%', '-50%'] }}
        transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
      >
        {[...items, ...items].map((item, i) => (
          <span key={i} className="marquee__item">
            {item}
            <span className="marquee__dot" />
          </span>
        ))}
      </motion.div>
    </div>
  )
}

// ── Main Landing Page ────────────────
export default function LandingPage() {
  const [loaded, setLoaded] = useState(false)
  const navigate = useNavigate()
  const containerRef = useRef(null)

  // GSAP scroll animations
  useEffect(() => {
    if (!loaded) return

    // Horizontal scroll on features??
    // Parallax lines
    gsap.utils.toArray('.landing-line').forEach((line, i) => {
      gsap.fromTo(
        line,
        { scaleX: 0 },
        {
          scaleX: 1,
          duration: 1.5,
          ease: 'power3.inOut',
          scrollTrigger: {
            trigger: line,
            start: 'top 85%',
            toggleActions: 'play none none none',
          },
        }
      )
    })

    return () => ScrollTrigger.getAll().forEach((st) => st.kill())
  }, [loaded])

  const features = [
    {
      icon: HiOutlineCpuChip,
      title: 'AI-Powered Answers',
      description: 'Ask questions in natural language. Our RAG pipeline retrieves relevant context and generates precise answers from your knowledge base.',
    },
    {
      icon: HiOutlineDocumentMagnifyingGlass,
      title: 'Smart Ingestion',
      description: 'Upload PDFs, DOCX, TXT, or images. Documents are automatically chunked, embedded, and indexed for semantic search.',
    },
    {
      icon: HiOutlineLockClosed,
      title: 'Role-Based Security',
      description: 'Fine-grained access control ensures employees only see documents they\'re authorized to access. Complete audit trail included.',
    },
    {
      icon: HiOutlineShieldCheck,
      title: 'Enterprise Audit',
      description: 'Every query is logged with user context, response time, and sources. Full transparency for compliance and governance.',
    },
    {
      icon: HiOutlineBoltSlash,
      title: 'Blazing Fast Cache',
      description: 'Redis-powered caching layer delivers sub-millisecond responses for repeated queries. Smart invalidation keeps answers fresh.',
    },
    {
      icon: HiOutlineSparkles,
      title: 'Semantic Vector Search',
      description: 'Powered by Qdrant and sentence transformers. Find answers based on meaning, not just keywords.',
    },
  ]

  return (
    <div className="landing-page" ref={containerRef}>
      {!loaded && <Loader onComplete={() => setLoaded(true)} />}

      {loaded && (
        <>
          <MagneticCursor />

          {/* ███ NAVBAR ███ */}
          <motion.nav
            className="landing-nav"
            initial={{ y: -80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="landing-nav__logo" data-magnetic>
              <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
                <circle cx="14" cy="14" r="12" stroke="#22c55e" strokeWidth="2" />
                <circle cx="14" cy="14" r="5" fill="#22c55e" />
              </svg>
              <span>Nexus</span>
            </div>
            <div className="landing-nav__links">
              <a href="#features" data-magnetic>Features</a>
              <a href="#about" data-magnetic>About</a>
              <a href="#stats" data-magnetic>Stats</a>
            </div>
            <motion.button
              className="landing-nav__cta"
              onClick={() => navigate('/login')}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              data-magnetic
            >
              Launch App <HiOutlineArrowUpRight />
            </motion.button>
          </motion.nav>

          {/* ███ HERO ███ */}
          <section className="hero">
            <div className="hero__3d">
              <Suspense fallback={null}>
                <Scene3D />
              </Suspense>
            </div>

            <div className="hero__content">
              <motion.div
                className="hero__badge"
                initial={{ opacity: 0, scale: 0.8, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ delay: 0.4, duration: 0.6 }}
              >
                <span className="hero__badge-dot" />
                Internal AI Knowledge Base
              </motion.div>

              <div className="hero__title-wrap">
                <RevealText delay={0.5}>
                  <h1 className="hero__title">
                    The future of
                  </h1>
                </RevealText>
                <RevealText delay={0.65}>
                  <h1 className="hero__title hero__title--accent">
                    knowledge access
                  </h1>
                </RevealText>
                <RevealText delay={0.8}>
                  <h1 className="hero__title">
                    is here.
                  </h1>
                </RevealText>
              </div>

              <motion.p
                className="hero__subtitle"
                initial={{ opacity: 0, y: 20, filter: 'blur(8px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                transition={{ delay: 1.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              >
                Ask questions. Get instant, AI-powered answers from your company's
                knowledge base — secured by role, logged for compliance.
              </motion.p>

              <motion.div
                className="hero__actions"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.3, duration: 0.6 }}
              >
                <motion.button
                  className="hero__cta-primary"
                  onClick={() => navigate('/login')}
                  whileHover={{ scale: 1.04, boxShadow: '0 0 60px rgba(34,197,94,0.3)' }}
                  whileTap={{ scale: 0.97 }}
                  data-magnetic
                >
                  Get Started
                  <HiOutlineArrowRight className="hero__cta-arrow" />
                </motion.button>
                <motion.a
                  href="#features"
                  className="hero__cta-secondary"
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.97 }}
                  data-magnetic
                >
                  Explore Features
                </motion.a>
              </motion.div>
            </div>

            {/* Scroll indicator */}
            <motion.div
              className="hero__scroll"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 2 }}
            >
              <motion.div
                className="hero__scroll-line"
                animate={{ scaleY: [0, 1, 0], y: [0, 0, 20] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              />
              <span>Scroll</span>
            </motion.div>
          </section>

          {/* ███ MARQUEE ███ */}
          <Marquee />

          {/* ███ FEATURES ███ */}
          <section className="features-section" id="features">
            <div className="features-section__header">
              <RevealText>
                <span className="section-label">CAPABILITIES</span>
              </RevealText>
              <RevealText delay={0.1}>
                <h2 className="section-title">
                  Built for the modern
                  <br />
                  <span className="section-title--accent">enterprise</span>
                </h2>
              </RevealText>
              <div className="landing-line" />
            </div>

            <div className="features-grid">
              {features.map((f, i) => (
                <FeatureCard key={i} {...f} index={i} />
              ))}
            </div>
          </section>

          {/* ███ ABOUT / HOW IT WORKS ███ */}
          <section className="about-section" id="about">
            <div className="about-section__inner">
              <div className="about-section__left">
                <RevealText>
                  <span className="section-label">HOW IT WORKS</span>
                </RevealText>
                <RevealText delay={0.1}>
                  <h2 className="section-title">
                    From document to
                    <br />
                    <span className="section-title--accent">instant answers</span>
                  </h2>
                </RevealText>
              </div>
              <div className="about-section__steps">
                {[
                  { num: '01', title: 'Upload', desc: 'Admins upload PDF, DOCX, TXT, or image files to the knowledge base.' },
                  { num: '02', title: 'Process', desc: 'Documents are extracted, chunked, and embedded into high-dimensional vectors.' },
                  { num: '03', title: 'Index', desc: 'Vectors are stored in Qdrant for lightning-fast semantic similarity search.' },
                  { num: '04', title: 'Query', desc: 'Employees ask natural language questions. The system retrieves relevant chunks and generates answers using an LLM.' },
                ].map((step, i) => (
                  <motion.div
                    key={i}
                    className="about-step"
                    initial={{ opacity: 0, x: 40 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: '-60px' }}
                    transition={{ delay: i * 0.15, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <span className="about-step__num">{step.num}</span>
                    <div>
                      <h4 className="about-step__title">{step.title}</h4>
                      <p className="about-step__desc">{step.desc}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
            <div className="landing-line" />
          </section>

          {/* ███ STATS ███ */}
          <section className="stats-section" id="stats">
            <RevealText>
              <h2 className="section-title section-title--center">
                Performance at <span className="section-title--accent">scale</span>
              </h2>
            </RevealText>
            <div className="stats-grid">
              <StatCounter value={384} label="Vector dimensions" index={0} />
              <StatCounter value={50} suffix="ms" label="Avg response time" index={1} />
              <StatCounter value={99} suffix="%" label="Uptime SLA" index={2} />
              <StatCounter value={10} suffix="k+" label="Docs supported" index={3} />
            </div>
          </section>

          {/* ███ CTA ███ */}
          <section className="cta-section">
            <ParallaxSection speed={0.3}>
              <div className="cta-section__inner">
                <motion.div
                  className="cta-section__glow"
                  animate={{
                    opacity: [0.3, 0.6, 0.3],
                    scale: [1, 1.1, 1],
                  }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                />
                <RevealText>
                  <h2 className="cta-section__title">
                    Ready to unlock your
                    <br />
                    organization's knowledge?
                  </h2>
                </RevealText>
                <motion.button
                  className="hero__cta-primary cta-section__btn"
                  onClick={() => navigate('/login')}
                  whileHover={{ scale: 1.05, boxShadow: '0 0 80px rgba(34,197,94,0.4)' }}
                  whileTap={{ scale: 0.97 }}
                  data-magnetic
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.3, duration: 0.6 }}
                >
                  Launch Project Nexus <HiOutlineArrowRight />
                </motion.button>
              </div>
            </ParallaxSection>
          </section>

          {/* ███ FOOTER ███ */}
          <footer className="landing-footer">
            <div className="landing-footer__inner">
              <div className="landing-footer__logo">
                <svg width="20" height="20" viewBox="0 0 28 28" fill="none">
                  <circle cx="14" cy="14" r="12" stroke="#22c55e" strokeWidth="2" />
                  <circle cx="14" cy="14" r="5" fill="#22c55e" />
                </svg>
                <span>Project Nexus</span>
              </div>
              <span className="landing-footer__copy">
                {new Date().getFullYear()} — Internal AI Knowledge Base
              </span>
            </div>
          </footer>
        </>
      )}
    </div>
  )
}
