import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Demo from "./components/Demo";
import { Method, Results, Team } from "./components/Sections";
import { Reveal } from "./components/ui";

export default function App() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <section id="demo" className="mx-auto max-w-[1200px] scroll-mt-20 px-3 pb-8 pt-6 md:px-8">
          <Reveal className="mb-8 px-2 md:px-0">
            <h2 className="text-3xl font-semibold tracking-tight md:text-[44px] md:leading-[1.1]">Try a question</h2>
            <p className="mt-4 max-w-[56ch] leading-relaxed text-muted">
              Pick an example or type your own. You will see how the question is linked, planned, checked and turned into SQL.
            </p>
          </Reveal>
          <Demo />
        </section>
        <Method />
        <Results />
      </main>
      <Team />
    </>
  );
}
