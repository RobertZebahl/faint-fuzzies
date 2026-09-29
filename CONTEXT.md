# Faint Fuzzies

A tool for maintaining a personal catalogue of sky objects and the observations made of them, and for publishing them on a website.

## Language

**Object**:
A thing in the sky that can be observed. It exists whether or not anyone has observed it, and may be known under different names in different catalogues.

**Group**:
An Object made up of member Objects, such as a multiple star system whose pairs are its members. Members remain Objects in their own right. The link between a Group and its members is a membership, not a Reference.
A Group exists as an Object only when the group itself can be observed as a whole, as with a multiple star
system or a compact galaxy group. A collection whose members are spread over the sky, such as the Local Group, is
only a Group name.

**Group name**:
The name of a collection of Objects, written on each member, whether or not the collection exists as an Object
of its own. The Local Group is a Group name; Hickson 44 is both a Group name and a Group.

**Alternative name**:
A name the user gives a double star Group, or a pair with no Group, beyond what the WDS itself provides -
or in place of a WDS name that is unwanted. It is kept in a file of its own; it merges into the Object's
names when loaded, the same as any other name of it, unless marked to replace the WDS's own names instead
(its WDS id is always kept, since that is the one stable identifier, and is never pushed out of its last
place by a merge). A name given to a Group also reaches each of its own pairs - a name common to the whole
system should read that way wherever one of its pairs is shown on its own, not only on the Group. A pair
keeps its own designation throughout; a replace also drops the name it replaced from every pair that
had it too (inherited identically from the WDS at conversion time), so a pair never keeps showing the
very name the Group's own entry replaced.

**Component**:
The letters naming which stars of a multiple star system an Object refers to (AB, AC, Aa-Ab). A name together with a Component identifies a member of a double star Group. The letters of a Component are unordered (AB names the same stars as BA), but its structure is not: AB-C and A-BC are different Components. An Observer may give `*` instead of a Component to mean that more than one was observed; the Observation then belongs to the Group as a whole, not to one pair.

**WDS id**:
The identifier of a double star system in the WDS, written with its prefix (for example WDS19307+2758). It is the name of the system's Group, and one of the names of each pair in it; it is always the last name in an Object's name list.

**Joined name**:
A name that stands for several Objects at once, written with " & " (`NGC6992 & NGC6995 & IC1340`). Each part is a
name of that Object too, so a name that refers to one part finds it. The parts are not looked up the other way round.

**Catalogue**:
A named list of Objects from one source. Every Catalogue uses the same common format, whatever its origin.

**Own catalogue**:
The Catalogue the user maintains by hand. Its Objects are the shared reference points for every Observer's
observations - except a double star matched to the WDS, which has no Object of its own there; its Own
observations are instead recorded in the Own catalogue by name and Component, attaching to the WDS Object
when loaded, the same way a Community observation does (see Own observation).

**External catalogue**:
A Catalogue published by a third party (SAC, UGC, Herschel, WDS, GCVS) and converted into the common format. Read-only reference data. Catalogues refer to each other's Objects by name.

**Reference**:
A direct link between Objects in different Catalogues that stand for the same thing in the sky, established by a shared name. References never exist within one Catalogue and are not transitive. A Group references only Groups, and a double star pair only a pair with the same Component (a pair without one is the pair AB). Because Groups are often named differently in different Catalogues, a Group also references the Groups whose members reference its members. The Observations of an Object can be seen from every Object it references.

**DSS image**:
An external reference image of an Object's sky position, fetched from the Digitized Sky Survey. Unlike a
Sketch, Photograph or Image, it shows the sky itself rather than depending on anything the user or
an Observer did. Available only for the Own catalogue and the UGC, SAC and Herschel catalogues, and only
for an Object whose size is known (its own size, or an explicit field of view override) - without one, no
image is fetched, and this is never flagged as a Finding, the same as any other reason none is fetched.

**Orbit diagram**:
A generated diagram of a WDS pair's computed orbit around its companion, plotted from published orbital
elements. Available only for pairs with known orbital elements. A pair has one Orbit diagram for each of its
Solutions that can be plotted.

**Solution**:
One published set of orbital elements for a WDS pair. A pair may have several. Those that can be plotted are
numbered in the order the catalogue lists them, but only when more than one can be plotted. A Solution that
cannot be plotted has no Orbit diagram and is not counted.

## Observing

**Observer**:
A person who makes Observations.

**Scope**:
An Observer's role, one of three: Owner (the user; at most one), Global (also counted on the Global
observation list, alongside any Project), or Project (the default; counted only on the Projects
contributed to).

**Global observer**:
An Observer with Global Scope. There is currently one.

**Observation**:
A record of one Observer observing one Object: an Own observation when the user made it, a Community
observation otherwise.

**Own observation**:
An Observation made by the user, recorded in the Own catalogue - the only kind that can be Private. It is
usually stored on its own Object there; a double star matched to the WDS has none, and is recorded by name
and Component instead, attaching to the WDS Object when loaded (see Own catalogue).

**Community observation**:
A Public Observation contributed by an Observer other than the user. It is attached to an Object (of the Own catalogue or, for double stars, the WDS) when loaded and is never stored in a Catalogue.

**Private observation**:
An Observation kept only in the user's own log. It is never published.

**Public observation**:
An Observation intended for publication. Every Community observation is one.

**Session**:
A period of observing at one place. A Private observation belongs to the Session that contains its date and time.

**Conditions**:
The sky readings (Bortle class, limiting magnitude, SQM, SQM-L, seeing) of a Session or of a Public observation.

**Local conditions near the object**:
Additional sky readings an Observation may give for the region right around its Object, distinct from its Conditions; they never replace the general ones. Public descriptions show them when they are present.

**Sketch**:
A hand-drawn illustration of what was seen, attached to a visual-method Observation. Stating the OPTIC used
is always required. An Observation may have several. A Sketch may show several Objects (two stars in one
field); it is then attached to an Observation of each, and is still one Sketch, counted once.

**Gallery group**:
A category of the sketch gallery: Carbon & Red Stars, Double Stars, Asterisms, Open Clusters, Globular
Clusters, Planetary Nebulae, Bright Nebulae, Dark Nebulae, Galaxies & Groups, Comets, Planets, Moon, Sun, or
Miscellaneous. An Object belongs to the first of these its types fit, in that order (a Carbon star that is
also a double star is a Red star). A Sketch is shown once in each Gallery group any of its Objects falls into,
titled with all its Objects.

**Photograph**:
A photographic image of what was seen, attached to a photographic-method Observation. An Observation may
have several.

**Image**:
A general informative image for the Object, not tied to what was seen. Unlike a Sketch or Photograph, it does
not record an observing session — but unlike them, it may accompany one: an Observation may combine an Image
with a Sketch and/or a Photograph. On the website the three always appear in the same order: Sketch,
Photograph, Image. An Image is optional on any Observation, including a Header.

**Header**:
A Public Own observation with no instrument and no Sketch or Photograph. It gives general information about
the Object for the website — text and, optionally, an Image — rather than reporting an observing
session. A Sketch or Photograph always means an observing session is being reported, whether or not the
instrument is known, so an observation carrying one is never a Header even without an OPTIC. An Object has at
most one Header. A Header is stored like an Observation but is never counted as one, and never makes an Object
published.

**Global observation list**:
The website's main list of Public observations, shown per Object. It holds the user's own Public observations and those of Global observers, but not those of Project-scope contributors. It covers every Object type with no exclusion by type; website generation may still leave some Object types off the Global page itself in favour of a dedicated page for them, but that is a website-generation concern, not a rule of list membership.

**Published**:
An Object is published only when it has at least one valid Observation, from any Observer; a Header is not an
Observation. This holds for the Global observation list, its Website lists and every Project. An Object with
only a Header is therefore never published, unless it is marked Publish without observation.

**Publish without observation**:
A mark the user puts on an Object so that the Global observation list (and its Website lists) publishes it
without any Observation, even without a Header, for instance because the Headers of related Objects refer to it.
Whether that makes sense is the user's decision. It does not apply to Projects and never makes an Invalid Object
valid.

**Website list**:
A named subset of the Global observation list with its own page, defined by a rule about the Object (its name,
type, group, size ratio or References) or about its Observations (whether any carries a public Sketch) - never
by who observed it. Objects by type (double stars, open clusters, …), special lists (Messier, Herschel 400,
Local Group, …) and the sketch galleries are all Website lists. Not to be
confused with a Project list, which is a subset of a Project.

**Red star**:
A Carbon star, or any star the user marks as red. The Red stars are the Website list of that name.

**Messier list**:
The Website list of Objects named Messier n, one row per Object. Two Objects may carry the same Messier number
(the Eagle Nebula and its cluster are both Messier 16), so the list may have more rows than distinct numbers;
its size is the number of distinct numbers.

**Statistics**:
The numbers of the website's home page: for each Object type (Double stars, Asterisms, Open clusters, Globular
clusters, Planetary nebulae, Bright nebulae, Dark nebulae, Galaxies, and Miscellaneous for every other Object)
the number of Objects and, in brackets, of Observations, in total and for each Observer of the Global
observation list. The total counts every Object of the Global observation list; an Observer's column counts
the Objects they observed. Headers are not Observations and never count, so an Object published only through
Publish without observation is in the total but in nobody's column. The app's Statistics screen shows its own,
finer breakdown of the same Global observation list (and, separately, of each Project and each Observer's own
Objects), by more Object types than this one lumps into Miscellaneous - the two do not use the same categories.

**Project**:
A themed collection of Public observations of selected Objects, contributed by several Observers and published as its own list. Currently Double Stars and Deep Sky With Binoculars. Every Project lists the user's own Public observations that fit its theme.

**Project list**:
A named subset of a Project's Objects, such as the double stars selected for binoculars, the colored double stars, or the multiple systems.

**Rating**:
An Observer's recommendation of an Object, from one to three stars. Only an Observer's highest Rating of an Object counts, and the Object's overall Rating is the average over all Observers. The user's own Rating is a personal marker stored on the Object, and Projects count it like any other Observer's. Deep Sky With Binoculars uses a separate binocular Rating, also stored on the Object, instead of it.

**Grade**:
An observation's verdict on how an Object went - a Private Grade (a number, see the README, "Private Grade") or a Public Grade (a Difficulty or Color, see the README, "Public Grade"), never both on the same observation, since a Private and a Public observation each record it differently. The website and the app show both under the one term "Grade".

**Seen**:
An Object is seen when any Private observation of it states a seen Private Grade or no Grade at all. Bright objects such as the Moon and planets carry no Grade, because a Grade makes no sense for them.

## Data quality

**Finding**:
A finding about the data: an Error, a Warning, or an Info. It is attached to the Object it concerns, or to one of that
Object's Observations. A Finding that concerns no Object (a Session, an Observer, a file) belongs to no Object. An Object is at the level
of its worst Finding, or of its Observations' worst: fine, info, warning or error.

**Error**:
A Finding that makes the Object or Observation it concerns Invalid. An Error that only a comparison of several
records or files shows (a missing image file, a missing position) marks the Object but does not make it Invalid.

**Warning**:
A Finding that leaves the Object or Observation valid; it is only marked.

**Info**:
A Finding that notes something true about the data without implying anything is wrong - the lowest level, below
a Warning. It leaves the Object or Observation exactly as valid as it would be without it.

**Invalid**:
An Object or Observation with an Error. It is kept and shown together with its Findings, but takes part in nothing
else: never in a Reference, a list, Statistics, a Rating or the website. A record without a usable name is
identified by its position in its file.

An Object with an invalid Observation is not Invalid itself, even when all its Observations are: it is marked as
containing invalid Observations, and it is not Published unless it has a valid Observation.
