# Abstract

Room-Scale Snake investigates whether an ordinary room can function as
both the display and the controller for an entertaining, responsive
game. A projector renders a Snake-like play-field on a floor or wall of
the Georgia Institute of Technology Aware Home. A Sensy One mmWave radar
presence sensor reports real-time coordinates for the player, mapping
their position onto calibrated floor zones for four-direction steering,
with the Aqara FP2 presence sensor as a fallback. An overhead camera
detects tagged physical objects such as portals and gates, and Home
Assistant coordinates Philips Hue lighting, Amazon Echo audio, and an
optional television display as synchronized feedback. Unlike a
conventional screen game, the physical room becomes part of the game
state. Tagged objects will function as collision boundaries and paired
portals, while key-and-gate interactions will be added after the core
sensing and projection loop is stable. Movable objects and a
second-player level-design mode will remain stretch goals. The project
contributes to a reproducible integration of projection, environmental
sensing, physical objects, and ambient actuation in one Aware Home room.
The team will implement a baseline movement-only condition and full
environment-integrated condition, then evaluate both system quality and
user/player experience. Technical acceptance criteria include at least
90 percent directional-zone accuracy, median sensor-to-projection
latency at or below 150 ms, 95th-percentile latency at or below 250 ms,
at least 95 percent successful ambient-device events, and no unhandled
failure in a 15-minute soak test. A counterbalanced within-subject study
with 4-8 adults will measure task completion, errors, perceived control,
physical presence, usability, and preference. Deliverables include the
playable prototype, calibration and obstacle-mapping tools, device
adapters, telemetry, documentation, an evaluation report, and a final
demonstration.

# Background and Motivation

Ubiquitous computing proposes that computation should be integrated into
everyday environments rather than demand attention and remain confined
to traditional desktop interfaces [@weiser1991computer]. The Georgia
Institute of Technology Aware Home was created as a living laboratory
for testing that proposition under realistic domestic conditions
[@kidd1999awarehome]. Room-Scale Snake uses this setting to ask a
focused design question: can a room's existing sensing and actuation
infrastructure support a legible game loop in which a player's movement,
real furniture, projected graphics, lighting, and sound form one
coherent interface?

The proposed experience occupies a middle ground between head-mounted
virtual reality and a conventional Kinect-style screen game. A headset
can provide precise tracking and visual isolation from the surroundings,
but it requires a worn display and makes the physical room and nearby
people less directly visible. A Kinect-style game offers familiar
full-body input, yet it usually centers interaction on one camera and
one television while the surrounding room remains of no use. Room-Scale
Snake instead keeps the player unencumbered and treats distributed
sensors, furnishings, projection surfaces, lights, and audio devices as
parts of one game state. This choice introduces its own limitations such
as coarser sensing, shadows, lighting variation, and registration drift,
which the project measures rather than presenting projection as
universally superior.

Projection research shows a progression from movable and tabletop
displays [@pinhanez2003steerable] [@wilson2005playanywhere] to systems
that reshape a larger physical environment. IllumiRoom extended
television content into a living room's periphery
[@jones2013illumiroom], while RoomAlive combined calibrated
projector-camera units and a shared room model to support touching,
stomping, dodging, and steering projected content [@jones2014roomalive].
ShareVR further demonstrated that floor projection can include
non-headset participants in a collocated immersive experience
[@gugenheimer2017sharevr]. More recently, Reality Distortion Room used
projection mapping and unencumbered interaction to influence locomotion
in a furnished room [@kim2023realitydistortion], confirming the
continuing relevance of spatial augmented reality while relying on a
much heavier multi-camera, multi-projector installation than this
project proposes. Together, these systems establish the promise of
shared room-scale interaction, but they also expose practical
challenges: projector registration, occlusion, lighting variation,
arbitrary furniture, and end-to-end delay. This proposal treats those
constraints as measured engineering variables rather than assuming that
a large image is automatically immersive.

Smart-home games add a second research thread. Hybrid gaming places
virtual rules, physical action, and social context in one loop
[@magerkurth2012hybrid], and IoT-game architectures separate sensing,
data services, game logic, and presentation so individual devices can
fail or change without collapsing the entire application
[@kim2018iotgames]. Modern radar work demonstrates that radio-frequency
sensing can recognize fine motion [@wang2016soli] and localize people
with specialized hardware [@wu2020mmtrack], while multi-radar fusion
improves robustness under occlusion but still requires a common
coordinate frame and empirical calibration of the room
[@canil2024oracle]. Therefore, the proposal makes zone-level steering,
rather than full-pose recognition, the required capability and treats
continuous tracking as optional.

The experiential gap is not simply that prior systems are old. A
projected game can still feel like a large screen if environmental cues
are decorative, delayed, or unrelated to player's actions. Multi-sensory
studies report stronger spatial presence or task performance when visual
and audio/tactile cues are credible and aligned
[@khenak2018spatialpresence] [@marucci2021multisensory], yet presence,
usability, and task performance remain distinct constructs
[@skarbez2017presence]. Room-Scale Snake addresses this gap by using
tagged physical objects as meaningful game elements, routing live room
events through a shared game state, synchronizing projection with
lighting and audio, and evaluating whether this integration improves
control, environmental awareness, and physical presence compared with a
movement-controlled projection baseline.

# Research Question, Aim, and Objectives

Research Question: Can a single-room projected Snake game that
integrates distributed smart-home sensing, registered physical objects,
and synchronized ambient feedback provide an understandable and
responsive experience, and a stronger sense that the room is part of the
game than a movement-controlled projection alone?

Aim: The team will build and evaluate one reliable, controller-free game
loop in one Aware Home room. The project does not claim that projection
is universally more immersive than Virtual Reality or that commodity
presence sensors equal camera-grade pose tracking. Its intended
contribution is a documented design and evidence-based assessment of a
lower-burden, shared alternative that turns installed room
infrastructure into both input and output.

Proposed System: Room-Scale Snake will use a primary mmWave presence
sensor to map the player's location into four steering zones. The game
computer will convert these events into directional commands, update the
Snake game state, and render the play-field through a projector. Home
Assistant will coordinate environmental outputs such as Philips Hue
lighting and audio feedback. Tagged physical objects will be registered
as obstacles or interactive game elements, allowing the room itself to
affect game play. The required prototype will provide a complete
one-player game-loop with calibrated steering zones, physical-object
interaction, synchronized environmental feedback, and timestamped event
logging. Paired portals and key-gate objects will be implemented after
the basic movement and collision loop is stable. Movable walls and live
second-player level editing are stretch goals pursued only if time
permits. This scope allows the team to evaluate the central research
question without making every proposed mechanic a pre-requisite for
success. At runtime, the Sensy One will report player coordinates
through Home Assistant to a local game adapter. The adapter will
timestamp and normalize each update, map the coordinates into four
calibrated steering zones, and apply de-bouncing and hysteresis before
passing a direction command to the game's state machine. The same state
machine will update the projected game and send event-specific commands
to the Philips Hue and audio adapters. During setup, a camera will
detect fiducial markers attached to physical objects, and a homography
transformation will convert their camera coordinates into locations on
the projected game grid. The resulting object map will remain fixed
during each round so that temporary detection errors do not unexpectedly
change the play-field. If player data becomes stale or devices fail to
respond, the game will pause or return the affected output to a neutral
state rather than guessing. Timestamped logs will connect sensor input,
game-state changes, rendered frames, device commands, and
acknowledgments so that the team can measure the accuracy and latency
objectives.

The three measurable objectives are:

- O1 - Playable loop: implement tutorial, start, play, collision, score,
  pause, restart, and end states; map four calibrated player zones to
  four-direction steering; and complete at least one five-minute round
  without a handheld controller.

- O2 - Environmental integration: steer the snake using a Sensy One
  mmWave radar (with the Aqara FP2 as a fallback); register at least two
  real household objects (including but not limited to furniture) as
  collision boundaries; support at least two interactive physical object
  types detected by an overhead camera (a portal pair that teleport the
  snake, a key that unlocks a matching gate, and if time permits, a
  movable wall that reshapes the game area during play); and trigger at
  least two ambient output classes (Hue lighting plus Echo audio or
  television) from game events.

- O3 - Technical performance: achieve at least 90-percent correct
  direction classification across at least 120 scripted zone
  transitions; sensor-to-projection latency of median $\leq$ 150 ms and
  95th percentile $\leq$ 250 ms; ambient-event latency of 95th
  percentile $\leq$ 750 ms; at least 95-percent successful device events
  across at least 100 triggers; median projection-registration error
  $\leq$ 5 cm across at least 12 control points; and no unhandled
  failure during a 15-minute soak test.

# Outcomes & Deliverables

The primary deliverable will be a functional prototype of the projected
Snake game operating in the Aware Home, where environmental sensors,
game software, and the projector will communicate in real time. In a
d-pad-style layout, the steering player stands in a neutral center zone,
and they can step into one of four surrounding zones on the floor to
turn the snake. Returning to the center will keep the snake moving in
its current direction. A Sensy One mmWave radar will measure player
coordinates, which the game will map to zones in software. A small
dead-zone between zones and a short de-bounce window, which accepts a
zone change once it has remained stable for some time, will prevent
unintended snake turns when the player stands near a boundary. If the
Sensy One proves to be unreliable, we intend to use the Aqara FP2 sensor
and its zone occupancy feature as a fallback. In earlier iterations of
the project, a keyboard will be used as an input for development and
testing purposes.

Before each round, a facilitator or second participant can arrange
tagged physical objects to shape the level. Dynamically modifying the
level while a round is in progress is treated as a stretch goal. These
objects will include pairs of portals that can teleport the snake, a key
that unlocks a matching gate once the snake collects it, and if time
permits, a movable wall that lets the designer shape the play-field
during play. Furniture in the play area will be registered as fixed
walls in the game. Game events will be able to cause ambient effects
through Home Assistant, such as dimming lights and closing shades when
the game begins to improve visibility of the projector display. Portals,
key-gate objects, and collisions will trigger sound effects, and an
optional television display will show a score indicator.

Additional deliverables include the software used to process sensor data
and run the game, documentation describing the system architecture and
hardware setup, and a final demonstration of the complete system. The
project will be evaluated primarily through the system responsiveness
and the reliability of the project, as well as successful completion of
the intended game-play loop. We will also conduct user testing to
evaluate whether players can understand the interaction method and
whether the physical environment contributes meaningfully to the gaming
experience. A specific evaluation metric we hope to achieve with the
user study is:

- With 4-8 adult participants, obtain at least 80% unassisted tutorial
  completion within two minutes, at least 80% completion of a full
  round, and median ease-of-control and instruction-understanding
  ratings of at least 5/7.

- Conduct a counterbalanced within-subject study with 4-8 adult
  participants comparing movement-only baseline with the complete
  environment-integrated game. Each participant will complete comparable
  rounds in both conditions, with condition order counterbalanced. The
  study will record completion time, collisions, assistance, and
  tracking corrections. After each condition, participants will rate
  ease of control, instruction clarity, environmental integration, and
  physical presence on seven-point scales, followed by an overall
  condition preference.

Through this project, we expect to develop an understanding of what it
takes to move computing off of a screen and into a real domestic
environment. Most of our previous experiences have treated
sensors/displays as peripherals, so building a game in the Aware Home
will require us to confront the gap between how these devices work in
isolation and how they behave together in a dynamic living environment.
Technically, we hope to learn how to coordinate many isolated devices
into one system while still maintaining a responsive experience. As for
design experience, we expect to learn how a physical environment changes
the way a player experiences this well-known game. Some questions we
intend to ask users include:

1.  Were you able to recognize boundaries as easily as on-screen ones?

2.  Did lighting/sound choices clarify game events?

3.  Did physical objects limit visibility of the playable area?

Through this, we hope to learn how to design feedback that players can
understand without instruction.

# Potential Challenges & Class Alignment

This project is a ubiquitous computing project because it distributes
computation across the physical environment rather than confining
interaction to a single device or screen. The projector, room sensors,
physical objects, lighting, audio devices, and Home Assistant
infrastructure collectively form the game interface. Physical objects
are not merely background scenery: tagged objects can function as
obstacles, paired portals, or keys and gates that modify the game state.
A movable wall and a second-player level-design mode may be explored as
stretch goals after the one-player game loop is reliable. In this way,
sensing, context awareness, embodied interaction, and distributed
devices combine to create a game that actively uses its environment.

The Aware Home is particularly appropriate for this investigation
because it provides sensing and actuation technologies embedded within a
realistic domestic environment. Much of the game can use infrastructure
already installed for everyday monitoring rather than requiring a
dedicated tracking installation. This supports a central principle of
ubiquitous computing: computation becomes part of the surrounding
environment and responds to people without requiring continuous
interaction with a conventional computer interface.

A major challenge will be coordinating heterogeneous devices. The
projector, mmWave presence sensor, camera, lighting, audio devices, and
game computer may use different communication protocols and update at
different rates. Home Assistant simplifies this integration but may also
become a point of failure. The system will therefore log device
acknowledgments, apply explicit timeouts, and preserve a playable
baseline mode when a nonessential ambient device becomes unavailable.
Devices requiring reconnection or configuration will be tested early in
coordination with the Aware Home mentor.

Sensing introduces additional context-awareness problems. The primary
mmWave sensor reports coordinates that must be mapped into four steering
zones. Because it may detect every person within range, bystanders or a
person arranging game objects could unintentionally steer the snake. The
play area will therefore use exclusion regions, clearly defined
participant positions, and software filtering to distinguish valid
control input from unrelated movement. Tagged objects will use fiducial
markers rather than color alone because projected light and changing
room illumination could otherwise interfere with camera-based detection.

Responsiveness is another important challenge. Each steering command
passes through several stages. The sensor detects the player, Home
Assistant relays the measurement, the game updates its state, and the
projector displays the resulting frame. Timestamps at each stage will
allow the team to identify bottlenecks and compare end-to-end
performance with the Objective O3 latency thresholds. Filtering also
creates a tradeoff. De-bouncing and hysteresis can prevent unintended
direction changes near zone boundaries, but excessive filtering may make
the controls feel sluggish. These parameters will be tuned using
recorded sensor traces and controlled movement tests. Cloud-dependent
devices such as an Amazon Echo may introduce additional delay, so
time-critical audio may use a local speaker if necessary.

The project must also maintain alignment between projected graphics and
the physical room. Previous projector-camera systems demonstrate both
the potential and difficulty of transforming ordinary surfaces into
interactive computational interfaces [@pinhanez2003steerable]. Because
an angled projector can distort the game grid through the keystone
effect, the system will use homography calibration to align projected
coordinates with the playing surface. Player shadows, moved furniture,
and Philips Hue lighting may also reduce visibility. A stable projector
position, controlled lighting, pre-session calibration checks, and
frozen per-round object maps will reduce these risks.

These challenges are part of the project's ubiquitous-computing
contribution rather than incidental implementation problems.
Context-aware systems must interpret imperfect information about people
and environments, while distributed devices must produce a coherent
response despite different protocols, delays, and failure modes.
Evaluating zone ambiguity, bystander interference, projection alignment,
device latency, and environmental change will therefore show both the
possibilities and the limitations of embedding an interactive system
within an ordinary room.

# Project Plan & Timeline

The plan protects a small vertical slice first: one sensor event changes
the snake, one projected collision is visible, and one ambient cue
confirms it. Static furniture collision mapping will be completed before
the midpoint checkpoint. Interactive portal and key/gate objects will be
completed before the November 20 feature freeze. The week of November 23
is deliberate schedule slack; no critical in-room task depends on
holiday access. The Gantt chart is provided in the appendix.

First, the team completes the literature review and inventory,
establishes device data contracts, and cable/safety requirements, and
calibrates the room transform, four steering zones, and at least two
physical obstacles. The phase exits when one sensor event and one
actuator can be logged and the median registration error is at most 5
cm.

Second, the team implements the tutorial, state machine, score,
collisions, pause/restart flow, and synthetic-input tests. In parallel,
the team adds the Sensy One adapter, with the Aqara FP2 adapter
maintained as a fallback, filtering, stale-input behavior, latency
logging, physical-object collisions, and Hue plus Echo/TV feedback. The
phase exits with a projected, movement-controlled round and a working
baseline/full-condition switch.

Finally, the team runs the technical matrix, 15-minute soak test, and
two-person pilot before the November 23 slack week. After any documented
mitigation, the team conducts 4-8 participant sessions beginning
November 30, freezes the dataset and build, and completes analysis,
reporting, the demonstration video, and the December 8 final
presentation.

# Gantt Chart

<figure id="fig:gantt" data-latex-placement="h">

<figcaption>Project timeline. Diamonds mark checkpoints; hatched bars
are scheduled slack or stretch goals.</figcaption>
</figure>
