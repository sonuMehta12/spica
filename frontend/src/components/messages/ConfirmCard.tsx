import type { ReactNode } from 'react';
import { BodyCard } from './ConfirmBody';
import { CommitmentCard } from './ConfirmCommitment';
import { DishSavedCard, MealCard, PantryMoveCard } from './ConfirmFood';
import { MemoryCard, PersonCard, PlaceCard, ProfileCard, ProjectCard, TaskCard } from './ConfirmMore';
import { PaymentCard, ProposalStack } from './ConfirmMoney';
import { field, type ConfirmActions, type ConfirmData } from './confirmKit';
import { color, font } from '../../theme';
import { agentCard } from './bubble';
import type { ConfirmMsg } from '../../types';

/**
 * A write the agent made, as the thing it wrote (spec/done/card-redesign.md).
 *
 * Each source gets its own line — a receipt for a payment, the task itself
 * for a task, a habit's count and week — instead of one form for all of them.
 * Every card reads its live row first and its payload only for what the row
 * cannot say, so an edit or a delete anywhere shows here. Guesses ask on the
 * card; quiet actions sit under it; nothing a person must answer is behind ⋮.
 * Change never fills the composer or opens a page: it hangs the row on the
 * composer as a pill, and the next sentence is about that row.
 *
 * `quiet`, when given, stands in for a card's own quiet actions: the first
 * run's answers all take Edit and Undo, the same two under every card
 * (spec/done/onboarding-goals.md § 3). Null draws none. It reaches the cards the
 * onboarding agent can write — a profile fact, a weight, a habit, a memory,
 * a task.
 */
export default function ConfirmCard({
  msg,
  data,
  actions,
  quiet,
}: {
  msg: ConfirmMsg;
  data: ConfirmData;
  actions: ConfirmActions;
  quiet?: ReactNode;
}) {
  switch (msg.source) {
    case 'paisa':
      if (msg.state === 'proposed') {
        return (
          <ProposalStack
            msgs={[msg]}
            tx={data.live.tx ? [data.live.tx] : []}
            deletedRows={data.live.deleted && msg.rowId ? [msg.rowId] : []}
            onConfirm={actions.onConfirm}
            onContext={actions.onContext}
            onRestore={actions.onRestore}
          />
        );
      }
      return <PaymentCard msg={msg} data={data} a={actions} />;
    case 'diet':
      // `keep_dish` writes a dish, not a meal: its one field is the dish's name.
      if (field(msg, 'name') && !field(msg, 'dish')) return <DishSavedCard msg={msg} data={data} />;
      return <MealCard msg={msg} data={data} a={actions} />;
    case 'body':
      return <BodyCard msg={msg} data={data} a={actions} quiet={quiet} />;
    case 'pantry':
      return <PantryMoveCard msg={msg} data={data} a={actions} />;
    case 'work':
      // A project card names the project; a task card names the project it sits in.
      if (field(msg, 'project')) return <TaskCard msg={msg} data={data} a={actions} quiet={quiet} />;
      return <ProjectCard msg={msg} data={data} />;
    case 'people':
      return <PersonCard msg={msg} data={data} />;
    case 'places':
      return <PlaceCard msg={msg} data={data} a={actions} />;
    case 'memory':
      return <MemoryCard msg={msg} data={data} a={actions} quiet={quiet} />;
    case 'profile':
      return <ProfileCard msg={msg} data={data} a={actions} quiet={quiet} />;
    case 'commitment':
      return <CommitmentCard msg={msg} data={data} a={actions} />;
    default:
      // A source the client has not learned yet: its lede still says what happened.
      return (
        <div style={agentCard('12px 14px')}>
          <span style={{ fontFamily: font.sans, fontSize: 14.5, lineHeight: '20px', color: color.ink }}>
            {(msg as ConfirmMsg).lede}
          </span>
        </div>
      );
  }
}
