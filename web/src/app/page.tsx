import type { Metadata } from "next";
import { JetBrains_Mono, Newsreader } from "next/font/google";
import Link from "next/link";
import { ContactForm, CopyEmail } from "@/components/landing/ContactForm";
import s from "@/components/landing/landing.module.css";

// The public homepage. The app's "who are you?" screen lives at /login (and the installed app opens there).

const serif = Newsreader({ subsets: ["latin"], variable: "--font-serif", display: "swap", axes: ["opsz"] });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap", weight: ["400", "500"] });

const TITLE = "VoiceMitra · A daily call that keeps medicine on time";
const DESCRIPTION =
  "VoiceMitra phones patients at dose time in Hindi or English, logs each dose and symptom, and brings in the doctor or family when something is wrong.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  // What a shared link shows (WhatsApp, LinkedIn, X). The picture is app/opengraph-image.png, captured from a
  // one-off HTML layout of the hero + live-call console (1200x630); X falls back to it as well.
  openGraph: { type: "website", url: "/", siteName: "VoiceMitra", title: TITLE, description: DESCRIPTION },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

function Mic() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}

const WAVE = [8, 16, 12, 20, 10];

export default function Home() {
  return (
    <div className={`${s.page} ${serif.variable} ${mono.variable}`}>
      <header className={s.in}>
        <nav className={s.nav} aria-label="Main">
          <Link className={s.logo} href="/"><span className={s.logoMark}><Mic /></span><span translate="no">VoiceMitra</span></Link>
          <div className={s.links}>
            <a href="#how">How it works</a>
            <a href="#who">For hospitals</a>
            <a href="#who">For families</a>
            <a href="#contact">Contact</a>
          </div>
          <div className={s.acts}>
            <Link className={`${s.b} ${s.ghost}`} href="/login">Log in</Link>
            <a className={`${s.b} ${s.dark}`} href="#contact">Book a demo</a>
          </div>
        </nav>
      </header>

      <main className={s.main}>
        <section className={`${s.in} ${s.hero}`}>
          <div className={s.orb} aria-hidden="true" />
          <span className={s.pill}>Hindi · English · Hinglish</span>
          <h1 className={s.h1}>A daily call that keeps <b>medicine on time</b></h1>
          <p className={s.sub}>
            VoiceMitra phones patients at dose time, asks if they took their medicine and how they feel, and brings in
            the doctor or family when something is wrong.
          </p>
          <p className={s.hindi} lang="hi">दवाई का समय, बस एक फ़ोन कॉल में।</p>
          <div className={s.ctas}>
            <a className={`${s.b} ${s.lg} ${s.dark}`} href="#contact">Book a demo</a>
            <a className={`${s.b} ${s.lg} ${s.ghost}`} href="#call">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4.5v15l13-7.5z" /></svg>
              See a sample call
            </a>
          </div>
        </section>

        <section className={`${s.in} ${s.show}`} id="call" aria-label="Example call">
          <div className={s.console}>
            <div className={s.ctop}>
              <span className={s.live}>LIVE · 00:41</span>
              <span>Kamla Devi · PCM 500 · 9:00 am</span>
              <span className={s.wave} aria-hidden="true">
                {WAVE.map((h, i) => <i key={i} style={{ height: h, animationDelay: `${i * 0.15}s` }} />)}
              </span>
            </div>
            <div className={s.cbody}>
              <div className={s.tx}>
                <p className={`${s.bubble} ${s.agent}`}><small>VoiceMitra</small>Namaste Kamla ji. Aapki dawai ka time ho gaya hai. PCM 500 leni hai, kya aapne le li?</p>
                <p className={`${s.bubble} ${s.pt}`}><small>Kamla ji</small>Haan, le li. Par seene mein thoda dard ho raha hai.</p>
                <p className={`${s.bubble} ${s.agent}`}><small>VoiceMitra</small>Main abhi doctor sahab ko isi call par jod raha hoon. Aap line par rahiye.</p>
                <span className={s.flag}>⚠ Red flag: chest pain → doctor joining the call</span>
              </div>
              <div className={s.side}>
                <div><h3>Dose</h3><div className={s.kv}><span>PCM 500</span><b className={s.ok}>Taken</b></div></div>
                <div><h3>Symptoms</h3><div className={s.kv}><span>Chest pain</span><b className={s.wr}>Mild · today</b></div></div>
                <div>
                  <h3>What happens next</h3>
                  <div className={s.kv}><span>Step</span><b className={s.mono}>escalate</b></div>
                  <div className={s.kv}><span>Action</span><b className={s.mono}>escalate_to_doctor</b></div>
                  <div className={s.kv}><span>Family</span><b>Notified</b></div>
                </div>
              </div>
            </div>
          </div>
          <p className={s.caption}>
            What the care team sees during a call: the conversation, the dose and symptoms it logged, and the moment it
            brought in a doctor.
          </p>
        </section>

        <section className={s.how} id="how">
          <div className={`${s.in} ${s.sec}`}>
            <div className={s.eyebrow}>How it works</div>
            <h2 className={s.secH} style={{ marginTop: 10 }}>One phone call, three jobs.</h2>
            <div className={s.steps}>
              <div className={s.step}><em>Step 1</em><h3>It calls at dose time</h3><p>The patient&apos;s phone rings like a normal call, at the times the doctor set. No app to learn, no screen to read.</p></div>
              <div className={s.step}><em>Step 2</em><h3>It listens and logs</h3><p>Taken, skipped or forgotten, plus any symptoms with how bad and how long, saved as a clear record.</p></div>
              <div className={s.step}><em>Step 3</em><h3>It gets help</h3><p>A red-flag symptom brings a doctor into the same call. A missed dose sends the family a message.</p></div>
            </div>
            <div className={s.never}>
              <span><b>It never</b> changes a dose.</span>
              <span><b>It never</b> gives a diagnosis.</span>
              <span><b>It always</b> escalates a red-flag symptom, whatever the conversation.</span>
            </div>
          </div>
        </section>

        <section className={`${s.in} ${s.sec} ${s.anchor}`} id="who">
          <h2 className={s.secH}>Made for the three people around every prescription.</h2>
          <div className={s.aud}>
            <div><div className={s.eyebrow}>Patients</div><h3>Just answer the phone</h3><p>Hindi or English, at the times the doctor set. No app to learn.</p><Link href="/who/patient">Open the patient app</Link></div>
            <div><div className={s.eyebrow}>Families</div><h3>Know they&apos;re okay</h3><p>Get a message if a dose is missed or something sounds wrong.</p><Link href="/who/caregiver">Caregiver sign in</Link></div>
            <div><div className={s.eyebrow}>Hospitals</div><h3>See adherence at a glance</h3><p>Every call logged, every red flag routed to the right doctor.</p><Link href="/login">Staff sign in</Link></div>
          </div>

          <div className={s.contact} id="contact">
            <div className={s.contactIntro}>
              <h2>Running a pilot at your clinic?</h2>
              <p>Tell us about your patients and what you&apos;d like to try. We&apos;ll set up a demo call, or help you get started with your family.</p>
              <CopyEmail />
              <div className={s.next}>
                <h3 className={s.nextTitle}>What happens next</h3>
                <ol>
                  <li><span className={s.nextNum}>1</span><span><b>We reply by email</b>Every message is read by a person, not a bot.</span></li>
                  <li><span className={s.nextNum}>2</span><span><b>A short demo call</b>We show a live reminder call, in Hindi or English.</span></li>
                  <li><span className={s.nextNum}>3</span><span><b>Set it up</b>If it fits, we add your patients, or your parent, and the calls start.</span></li>
                </ol>
              </div>
            </div>
            <ContactForm />
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <div className={s.in}>
          <span>© 2026 VoiceMitra</span>
          <div className={s.fl}>
            <a href="#how">How it works</a>
            <Link href="/login">Log in</Link>
            <a href="#contact">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
