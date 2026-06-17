# Target markets and positioning

## The customer in one sentence

> An organization that runs critical software, can't tolerate
> performance jitter, has to pass a certification audit, increasingly
> wants local AI as part of the stack, and is paranoid about its
> attack surface.

That excludes consumer desktops on purpose. It includes:

- **Defense.** Mission systems, sensor fusion boxes, autonomous
  vehicles, command-and-control consoles.
- **Aerospace.** Avionics, ground stations, simulation, anything
  DO-178C-shaped.
- **Industrial control.** Robotics, factory automation, process
  control where downtime is catastrophic.
- **Medical devices.** Imaging consoles, surgical assistants,
  diagnostics with embedded AI components.
- **Autonomous systems.** Drones, ground vehicles, marine systems,
  field robotics.

Anywhere "predictable performance under load" is a procurement
criterion, Yantra has a story.

## Why these markets, specifically

Three structural facts about Yantra map onto three pain points these
customers actually have:

### Predictable performance → addresses jitter

Conventional OSes trade predictability for flexibility. They are
brilliant at running 100 Chrome tabs and a video call simultaneously.
They are mediocre at guaranteeing that a control loop's deadline is
met when something else on the box gets busy. Yantra inverts that
trade: fixed allocations, no degradation, admission failure instead
of throttling. New launches that can't fit fail loudly; running
processes are not affected.

That property is, by itself, worth a lot to a control-systems
customer.

### Verifiability → addresses certification

DO-178C-style certification is a multi-year, multi-million-dollar
activity. The single biggest cost driver is the size and complexity
of the trusted base. Yantra ships a small kernel, a small set of
critical processes, and a tensor-normal-form representation that an
SMT-style toolchain can actually reason about.

You don't get a certification for free. You do get a much more
favorable starting point than "here is a Linux kernel, good luck."

### Air-gap-friendly attack surface → addresses procurement security

Defense and industrial customers assume their machines are eventually
adversarial environments. The fewer code paths, the better. Yantra:

- Has no `eval`, no service workers, no runtime code injection.
- Has no package-manager footprint at runtime (apps are AOT-compiled
  at install).
- Has a small syscall surface.
- Has no Chromium attack surface and no V8.

"It can't run your existing software" is normally a deal-breaker. In
this market it is the same sentence as "it can't run your existing
malware". The incompatibility is the feature.

## Where Yantra is *not* a fit

It is helpful to be clear about this so we don't waste time on the
wrong sales conversations:

- **Consumer general-purpose desktops.** The "you can't open 100 tabs"
  property is the wrong way around for this market.
- **Compatibility-first enterprises.** Anyone whose primary
  requirement is "must run our existing 200-app Windows fleet" is not
  the customer.
- **Mass-market gaming.** AAA games rely on architectures that we
  explicitly do not chase. Indie / browser games (WebGL + WebAssembly)
  work, but the gaming-PC market segment is wrong.
- **Cloud-scale fungible compute.** Yantra is for the box; it is not
  the next AWS Lambda runtime.

## The ChromeOS comparison

Because the GUI is "everything is a browser", people will reflexively
compare Yantra to ChromeOS. The comparison is the punchline of the
pitch:

| | ChromeOS | Yantra |
|---|---|---|
| **Surface area** | Browser-only userspace | Browser-only userspace |
| **Why** | Cheapest possible thin client | Best possible critical-systems endpoint |
| **Local AI** | Cloud-dependent | Native, first-class |
| **3D / WebGL** | GPU through browser pipeline | Same matrix substrate as the rest of the OS |
| **Verifiability** | None | Cleanly verifiable kernel + critical processes |
| **Hardware target** | Chromebooks (cheap) | High-end GPU / analog substrate (expensive) |
| **Software model** | Web apps + Linux compat | AOT-compiled JS/TS + Sutra-native |
| **Position** | Cheapest | Best |

The elevator pitch that lands is: "It looks like ChromeOS to your
users. It is the opposite of ChromeOS in every way that matters
underneath."

## Pricing and licensing

Open-source the OS. Sell the things customers in this market actually
buy:

- **Hardware.** The reference Yantra appliance, validated for its
  certification target.
- **Support contracts.** Same model as Red Hat, except the codebase
  is much smaller and the things going wrong are much weirder.
- **Certification packages.** The artefacts and consulting needed to
  get a Yantra-based system through a specific certification
  audit.
- **Custom kernel/critical-process work.** Per-engagement.

The hardware is not cheap. A box that includes a Yantra-suitable GPU
plus an analog accelerator (when those land) is north of consumer
pricing. That's fine — the customers in this market do not buy on
price, they buy on whether you survive their qualification process.

## Open questions

- **First lighthouse customer.** Who is the first reference deployment
  that takes Yantra seriously? An academic / lab partnership? A
  defense prime as a research contract? An industrial automation
  vendor?
- **Open-source vs. dual-license.** "OS is open, hardware/services
  closed" is the default. There may be specific subsystems (the
  certification toolchain, for example) where dual-licensing makes
  more sense.
- **Compliance roadmap.** Which certifications are realistic to
  pursue first? FIPS 140-3 for the crypto bits, Common Criteria, then
  DO-178C? The order matters and we don't have it locked.
