import SectionGrid from './SectionGrid';
import DishesSection from './DishesSection';
import PantrySection from './PantrySection';
import PeopleSection from './PeopleSection';
import PlacesSection from './PlacesSection';
import WorkoutsSection from './WorkoutsSection';
import SectionList from './SectionList';
import CommitmentsSection from '../commitments/CommitmentsSection';
import type { LineHandlers } from '../commitments/CommitmentLines';
import SourceBars from './SourceBars';
import PageHeader from '../PageHeader';
import { cardHeading } from '../messages/bubble';
import { color, inset, radius, space } from '../../theme';
import {
  SECTION_LABELS,
  itemsOf,
  sections,
  sourceRows,
  type Section,
} from '../../vault/stats';
import type { ItemKind, SavedItem } from '../../data/vault';
import type { CommitmentsPage, DishRow, ExerciseRow, PantryMoveRow, PantryRow, PersonRow, PlaceRow } from '../../data/api';
import type { Edits } from './PeopleSection';

interface Props {
  library: SavedItem[];
  /** The real pantry, from the moves ledger. `pantry` above is seed data. */
  pantryRows: PantryRow[];
  pantryMoves: PantryMoveRow[];
  /** The deck's anchor day — "2 days left" must count from the same today. */
  pantryToday: string;
  onPantryMove: (foodId: string, grams: number, kind: 'purchase' | 'opening') => Promise<boolean>;
  onUndoPantryMove: (id: string) => void;
  onAddFood: (name: string, quantity?: number, staple?: boolean, unit?: string) => Promise<boolean>;
  onPantrySettings: (id: string, reorder: number | null, shelfLife: number | null) => Promise<boolean>;
  onSetStaple: (id: string, staple: boolean) => Promise<boolean>;
  onStopTracking: (id: string) => void;
  onLoadPantryMoves: (foodId?: string) => void;
  dishes: DishRow[];
  onToggleSaveDish: (id: string) => void;
  people: PersonRow[];
  onFilePerson: (id: string, patch: Edits) => Promise<boolean>;
  onAddPerson: (name: string, patch: Edits) => Promise<boolean>;
  exercises: ExerciseRow[];
  onDidExercise: (id: string) => void;
  onAddExercise: (row: {
    name: string;
    kind: string | null;
    muscle_group: string | null;
    equipment: string | null;
    typical_minutes: number | null;
    steps: string | null;
    source_url: string | null;
  }) => Promise<boolean>;
  /** This month's commitments, live. */
  commitments: CommitmentsPage | null;
  onAddCommitment: () => void;
  commitmentHandlers: LineHandlers;
  places: PlaceRow[];
  onAddPlace: (row: { name: string; lat: number; lng: number; kind: string | null;
                      address: string | null; source: string }) => Promise<boolean>;
  onPatchPlace: (id: string, patch: { name?: string; kind?: string | null;
                                      counterparty_id?: string | null; note?: string | null;
                                      radius_m?: number }) => Promise<boolean>;
  onDeletePlace: (id: string) => void;
  /** null = the overview; otherwise the section this page is. Each is its own stack entry. */
  section: Section | null;
  /** A tile: its section, pushed over the overview. */
  onSection: (s: Section) => void;
  onDrop: (id: string) => void;
  /** What ← returns to — the menu from the overview, the overview from a section. */
  backTo: string;
  onBack: () => void;
}

const sectionTitle = {
  ...cardHeading,
  marginBottom: 8,
};

export default function DataPage({
  library,
  pantryRows,
  pantryMoves,
  pantryToday,
  onPantryMove,
  onUndoPantryMove,
  onAddFood,
  onPantrySettings,
  onSetStaple,
  onStopTracking,
  onLoadPantryMoves,
  dishes,
  onToggleSaveDish,
  people,
  onFilePerson,
  onAddPerson,
  exercises,
  onDidExercise,
  onAddExercise,
  commitments,
  onAddCommitment,
  commitmentHandlers,
  places,
  onAddPlace,
  onPatchPlace,
  onDeletePlace,
  section,
  onSection,
  onDrop,
  backTo,
  onBack,
}: Props) {

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={section ? SECTION_LABELS[section] : 'Your data'}
      tabIndex={-1}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 80,
        background: color.paper,
        display: 'flex',
        flexDirection: 'column',
        padding: `${inset.top} 0 0`,
        animation: 'fadeup 0.28s cubic-bezier(0.3,0.7,0.3,1)',
        outline: 'none',
      }}
    >
      <div style={{ padding: `0 ${space.gutter}px 16px`, flex: '0 0 auto' }}>
        <PageHeader
          back={{ label: backTo, onClick: onBack }}
          eyebrow="Your data"
          title={section ? SECTION_LABELS[section] : 'Everything'}
        />
      </div>

      {/* One scroller per level: the overview keeps its place while a section is open over it. */}
      <div className="scroll-y" style={{ flex: 1, padding: `0 ${space.gutter}px ${inset.bottom}` }}>
        {section === 'commitments' ? (
          <CommitmentsSection page={commitments} onAdd={onAddCommitment} handlers={commitmentHandlers} />
        ) : section === 'place' ? (
          <PlacesSection
            places={places}
            people={people}
            onAdd={onAddPlace}
            onPatch={onPatchPlace}
            onDelete={onDeletePlace}
          />
        ) : section === 'workout' ? (
          <WorkoutsSection exercises={exercises} onDid={onDidExercise} onAdd={onAddExercise} />
        ) : section === 'people' ? (
          <PeopleSection people={people} onFile={onFilePerson} onAdd={onAddPerson} />
        ) : section === 'recipe' ? (
          <DishesSection dishes={dishes} pantry={pantryRows} onToggleSave={onToggleSaveDish} />
        ) : section === 'pantry' ? (
          <PantrySection
            rows={pantryRows}
            moves={pantryMoves}
            today={pantryToday}
            onMove={onPantryMove}
            onUndoMove={onUndoPantryMove}
            onAdd={onAddFood}
            onSettings={onPantrySettings}
            onSetStaple={onSetStaple}
            onStopTracking={onStopTracking}
            onLoadMoves={onLoadPantryMoves}
          />
        ) : section ? (
          <SectionList
            items={itemsOf(section as ItemKind, library)}
            onDrop={onDrop}
          />
        ) : (
          <>
            <div style={sectionTitle}>Your things</div>
            <SectionGrid items={sections(library, pantryRows, dishes, people, exercises, places, commitments)} onOpen={onSection} />

            {/* Every section reads a real table now, so the seeded library is
                empty and this counts nothing. Hidden rather than deleted: it is
                still the only picture of what the capture extension is for, and
                it fills again the moment the extension saves anything. */}
            {library.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <div style={sectionTitle}>Where it came from</div>
                <div
                  style={{
                    background: color.white,
                    border: `1px solid ${color.line}`,
                    borderRadius: radius.card,
                    padding: 14,
                  }}
                >
                  <SourceBars rows={sourceRows(library)} />
                </div>
              </div>
            )}

            <div
              style={{
                fontSize: 12.5,
                lineHeight: 1.6,
                color: color.muted,
                marginTop: 20,
                paddingTop: 14,
                borderTop: `1px solid ${color.line}`,
              }}
            >
              All of this is yours. Whatever the extension catches lands here — to remove
              anything, press <b style={{ fontWeight: 500 }}>×</b> and it goes at once.
            </div>

            <div style={{ height: 18 }} />
          </>
        )}
      </div>
    </div>
  );
}
