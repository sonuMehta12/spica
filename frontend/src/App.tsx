import Conversation from './components/Conversation';
import Drawer from './components/Drawer';
import Toast from './components/Toast';
import Header from './components/Header';
import InputBar from './components/InputBar';
import Layer from './components/Layer';
import ModeDeck from './components/ModeDeck';
import ReportPage from './components/report/ReportPage';
import DataPage from './components/vault/DataPage';
import ProfilePage from './components/ProfilePage';
import CommitmentSheet from './components/commitments/CommitmentSheet';
import type { LineHandlers } from './components/commitments/CommitmentLines';
import { signOut } from './data/api';
import { keyOf, titleOf, useBack, useFocusReturn, type Screen } from './state/nav';
import { usePersonaOS } from './state/usePersonaOS';
import { useViewportHeight } from './lib/useViewportHeight';
import { inset, space } from './theme';
import type { Tx } from './types';

/**
 * Paisa Tracker — Personal OS.
 * Agent hi app hai: one conversation, and a swipeable deck of modes on top of it.
 */
export default function App({ onSignedOut }: { onSignedOut: () => void }) {
  const { state, view, suggestions, limit, actions } = usePersonaOS();
  useViewportHeight();
  useFocusReturn();

  // One set of commitment verbs for every surface that lists them — the Your
  // data page and the chat card — and one way to start one from a payment.
  const lineHandlers: LineHandlers = {
    onEdit: (c) => actions.openCommitmentSheet({ editing: c, payment: null }),
    onSkip: (c, skipped) => void actions.skipCommitment(c.id, skipped),
    onRepeat: (c, repeats) => void actions.repeatCommitment(c.id, repeats),
    onDelete: (c) => void actions.removeCommitment(c.id),
  };
  const makeFromPayment = (t: Tx) =>
    actions.openCommitmentSheet({
      editing: null,
      payment: { id: t.id, name: t.name, category: t.cat, amountPaise: Math.round(t.amt * 100) },
    });
  // The categories the ledger already uses, for the sheet's picker.
  const usedCategories = [
    ...(state.commitments?.items.filter((c) => c.source === 'commitment').map((c) => c.category) ?? []),
    ...[...state.tx, ...state.committedTx].map((t) => t.cat),
  ];

  // Home's open chat tray closes on Escape, as a page's open row does.
  useBack(state.openRow != null, () => state.openRow && actions.toggleRow(state.openRow));

  /** One composer, placed wherever it is needed — home, or over the top page. */
  const composer = (onSend: () => void, focusOnMount = false) => (
    <InputBar
      typed={state.typed}
      focusKey={state.composeFocus}
      focusOnMount={focusOnMount}
      onType={actions.setTyped}
      onSend={onSend}
      onMic={actions.tapMic}
      onMedia={actions.pickMedia}
      canLog={view.canLog}
      hint={view.composerHint}
      onComposing={actions.setComposing}
      editing={state.editing?.label ?? null}
      onCancelEdit={actions.cancelEdit}
      context={state.context}
      onClearContext={actions.clearContext}
    />
  );

  /**
   * A page's composer asks the agent, and the answer lands in the thread, so
   * an ask leaves every page for Home. A correction stays: the row it fixes
   * is on this page, and updates in place.
   */
  const pageComposer = composer(actions.sendFromPage);

  const last = state.stack.length - 1;
  /** One screen of the stack. `backTo` names what its ← returns to. */
  const screen = (sc: Screen, i: number) => {
    const top = i === last;
    const backTo = titleOf(state.stack[i - 1]);
    const onBack = () => actions.pop(sc);
    switch (sc.kind) {
      case 'menu':
        return (
          <Drawer
            top={top}
            userName={state.profile.displayName}
            avatarUrl={state.profile.avatarUrl}
            onClose={onBack}
            onRow={actions.openMenuRow}
            onSignOut={() => {
              actions.closeAll();
              void signOut().finally(onSignedOut);
            }}
          />
        );
      case 'report':
        return (
          <ReportPage
            mode={sc.mode}
            range={state.reportRange}
            tx={state.tx}
            committedTx={state.committedTx}
            meals={state.meals}
            todos={state.todos}
            habitLogs={state.habitLogs}
            pending={state.pending}
            borrowed={state.borrowed}
            repayments={state.repayments}
            limit={limit}
            onMode={actions.setReportMode}
            onRange={actions.setReportRange}
            backTo={backTo}
            onBack={onBack}
            onEdit={actions.editRow}
            onDelete={actions.deleteAny}
            onRepaid={actions.markRepaid}
            onAddOpen={actions.addOpen}
            onGift={actions.gift}
            onUndoRepayment={actions.undoRepayment}
            commitments={state.commitments?.items ?? []}
            commitmentsPage={state.commitments}
            commitmentHandlers={lineHandlers}
            onAddCommitment={() => actions.openCommitmentSheet({ editing: null, payment: null })}
            onLink={actions.linkPayment}
            onMake={makeFromPayment}
            composer={top ? pageComposer : null}
          />
        );
      case 'data':
        return (
          <DataPage
            library={state.library}
            pantryRows={state.pantry}
            pantryMoves={state.pantryMoves}
            pantryToday={view.anchorDay}
            onPantryMove={actions.addPantryMove}
            onUndoPantryMove={actions.undoPantryMove}
            onAddFood={actions.addPantryFood}
            onPantrySettings={actions.savePantrySettings}
            onSetStaple={actions.setStaple}
            onStopTracking={actions.stopTrackingFood}
            onLoadPantryMoves={actions.loadPantryMoves}
            dishes={state.dishes}
            onToggleSaveDish={actions.toggleSaveDish}
            people={state.people}
            onFilePerson={actions.filePerson}
            onAddPerson={actions.addPerson}
            exercises={state.exercises}
            onDidExercise={actions.didExerciseOnce}
            onAddExercise={actions.addExercise}
            commitments={state.commitments}
            onAddCommitment={() => actions.openCommitmentSheet({ editing: null, payment: null })}
            commitmentHandlers={lineHandlers}
            places={state.places}
            onAddPlace={actions.addPlace}
            onPatchPlace={actions.editPlace}
            onDeletePlace={actions.removePlace}
            section={sc.section}
            onSection={actions.openDataSection}
            onDrop={actions.dropItem}
            backTo={backTo}
            onBack={onBack}
          />
        );
      case 'profile':
        return (
          <ProfilePage
            profile={state.profile}
            memories={state.memories}
            weighIns={state.weighIns}
            group={sc.group}
            focus={sc.focus}
            top={top}
            onSaveField={actions.saveField}
            onSaveWeighIn={actions.saveWeighIn}
            onDeleteWeighIn={actions.removeWeighIn}
            onSaveMemory={actions.saveMemory}
            onAddMemory={actions.addMemoryRow}
            onDeleteMemory={actions.removeMemory}
            habits={state.habits}
            onAddHabit={actions.addHabit}
            onEditHabit={actions.editHabit}
            onFlipHabit={(id, direction) => actions.editHabit(id, { direction })}
            onDeleteHabit={actions.removeHabit}
            onProjectsChanged={() => void actions.reloadDeck()}
            schedules={state.schedules}
            onEditSchedule={actions.editSchedule}
            onGroup={actions.openProfileGroup}
            backTo={backTo}
            onBack={onBack}
            // Rows edit in place; the composer here is for asking the agent.
            composer={top ? pageComposer : null}
          />
        );
      case 'sheet':
        return (
          <CommitmentSheet
            sheet={sc.sheet}
            usedCategories={usedCategories}
            onSave={(draft, editing, paymentId) => actions.saveCommitment(draft, editing, paymentId, sc)}
            onClose={onBack}
          />
        );
    }
  };

  return (
    <div className="app-shell">
      {/* Home. Under any open screen it stays as it was, out of reach. */}
      <div
        inert={state.stack.length > 0}
        aria-hidden={state.stack.length > 0 || undefined}
        style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      >
        {/* The menu stays put — only the deck stands down while composing. */}
        <div style={{ flex: '0 0 auto', padding: `${inset.top} ${space.gutter}px 0` }}>
          <Header
            onMenu={actions.openMenu}
            onClear={actions.clearConversation}
            canClear={state.chat.length > 1}
            clearing={state.chatClearing}
          />
        </div>

        {/* The whole deck — card and dots — folds away while composing, so only
            the conversation is left. The menu above stays put. */}
        <div
          // Collapsed controls leave the tab order and stop taking taps.
          inert={state.composing}
          style={{
            flex: '0 0 auto',
            display: 'grid',
            gridTemplateRows: state.composing ? '0fr' : '1fr',
            opacity: state.composing ? 0 : 1,
            transition:
              'grid-template-rows 0.34s cubic-bezier(0.25,0.8,0.3,1), opacity 0.2s ease',
          }}
        >
          {/* The spacing lives on an inner box: padding on the grid item
              itself would survive the 0fr collapse and leave a gap. */}
          <div style={{ overflow: 'hidden', minHeight: 0 }}>
            <div style={{ padding: `0 ${space.gutter}px ${space.deckToThread}px` }}>
            <ModeDeck
              heroes={view.heroes}
              index={view.index}
              onIndex={actions.setModeByIndex}
              range={state.range}
              onRange={actions.setRange}
              moreOpen={view.moreOpen}
              onToggleMore={actions.toggleMore}
              onToggleTask={actions.toggleTodo}
              onSeeAllTasks={actions.showWorkTasks}
              onEditGoal={actions.editGoal}
              onEditTargets={actions.editTargets}
              onOpenReport={actions.openReport}
            />
            </div>
          </div>
        </div>

        <Conversation
          messages={state.chat}
          greetBody={view.greetBody}
          suggestions={suggestions}
          listening={state.listening}
          phase={state.phase}
          // Both lists: a payment counted toward a commitment must still resolve.
          tx={[...state.tx, ...state.committedTx]}
          meals={state.meals}
          todos={state.todos}
          // The rest of what the cards read live — habits and their logs,
          // pins, people, the pantry, the month's limit — straight from state.
          cardRows={state}
          openRow={state.openRow}
          onToggleRow={actions.toggleRow}
          onDelete={actions.deleteRow}
          onEdit={actions.editRow}
          onLinkPayment={actions.linkPayment}
          onMakeCommitment={makeFromPayment}
          commitmentHandlers={lineHandlers}
          onToggleTodo={actions.toggleTodo}
          // Change hangs the row on the composer; Undo on a removed row restores it.
          onContext={actions.setContext}
          onRestore={actions.restoreRow}
          onAnswer={actions.answer}
          onDismissCompose={() => actions.setComposing(false)}
          fetchedTx={state.fetchedTx}
          fetchedMeals={state.fetchedMeals}
          deletedRows={state.deletedRows}
          suggestLogged={state.suggestLogged}
          pendingLogs={state.pendingLogs}
          onConfirmRow={actions.confirmRow}
          onDeleteConfirm={actions.deleteConfirmRow}
          onLogSuggested={actions.logSuggested}
          onSaveSuggested={actions.saveSuggested}
          onDismissSuggested={actions.dismissSuggested}
          onNeedRows={actions.ensureRows}
          onRetry={actions.retry}
          chatHasMore={state.chatHasMore}
          chatLoadingOlder={state.chatLoadingOlder}
          chatCleared={state.chatCleared}
          onLoadOlder={actions.loadOlderChat}
        />
      </div>

      {/* Back on Home after an ask from a page, the cursor is waiting in it — the answer is in the thread. */}
      {state.stack.length === 0 && composer(actions.send, state.composing)}

      {state.stack.map((sc, i) => (
        <Layer key={`${i}:${keyOf(sc)}`} depth={i + 1} top={i === last}>
          {screen(sc, i)}
        </Layer>
      ))}

      {/* Above every screen: a refusal raised on a page is seen on that page. */}
      <Toast toast={state.toast} onDismiss={actions.dismissToast} />
    </div>
  );
}
