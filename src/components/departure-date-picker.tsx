import { useI18n } from '@/i18n';
import { useState } from 'react';
import { Keyboard, StyleSheet, TouchableOpacity, View } from 'react-native';
import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';

export function localDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function DepartureDatePicker({ value, onChange, disabled, onCalendarLayout }: { value: string; onChange: (value: string) => void; disabled: boolean; onCalendarLayout?: () => void }) {
  const { t, locale } = useI18n();
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => new Date(`${value}T12:00:00`));
  const today = localDate(new Date());
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const previousAllowed = month.getFullYear() > new Date().getFullYear() || (month.getFullYear() === new Date().getFullYear() && month.getMonth() > new Date().getMonth());
  return (
    <View style={styles.container}>
      <ThemedText type="smallBold">{t("DEPARTURE DATE")}</ThemedText>
      <TouchableOpacity accessibilityRole="button" accessibilityLabel={t("Choose departure date")} disabled={disabled}
        style={[styles.field, { backgroundColor: theme.background, borderColor: theme.backgroundSelected }]}
        onPress={() => { if (!open) { Keyboard.dismiss(); setMonth(new Date(`${value}T12:00:00`)); } setOpen(!open); }}>
        <ThemedText>{new Date(`${value}T12:00:00`).toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</ThemedText>
        <ThemedText>▾</ThemedText>
      </TouchableOpacity>
      {open && !disabled && <View onLayout={onCalendarLayout} style={[styles.calendar, { backgroundColor: theme.background }]}>
        <View style={styles.navigation}>
          <TouchableOpacity accessibilityRole="button" accessibilityLabel={t("Previous month")} disabled={!previousAllowed}
            style={[styles.arrow, !previousAllowed && { opacity: 0.3 }]} onPress={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ThemedText>‹</ThemedText></TouchableOpacity>
          <ThemedText type="smallBold">{month.toLocaleDateString(locale, { month: 'long', year: 'numeric' })}</ThemedText>
          <TouchableOpacity accessibilityRole="button" accessibilityLabel={t("Next month")} style={styles.arrow}
            onPress={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ThemedText>›</ThemedText></TouchableOpacity>
        </View>
        <View style={styles.grid}>
          {Array.from({ length: 7 }, (_, index) => new Date(2026, 0, 5 + index).toLocaleDateString(locale, { weekday: 'short' })).map((label, index) => <View key={`label-${index}`} style={styles.cell}><ThemedText type="small" themeColor="textSecondary">{label}</ThemedText></View>)}
          {Array.from({ length: Math.ceil((offset + count) / 7) * 7 }, (_, index) => {
            const day = index - offset + 1;
            if (day < 1 || day > count) return <View key={index} style={styles.cell} />;
            const date = localDate(new Date(month.getFullYear(), month.getMonth(), day));
            const past = date < today;
            const selected = date === value;
            return <TouchableOpacity key={index} accessibilityRole="button" accessibilityLabel={date} accessibilityState={{ selected, disabled: past }} disabled={past}
              style={[styles.cell, selected && styles.selected, past && { opacity: 0.25 }]}
              onPress={() => { onChange(date); setOpen(false); }}><ThemedText type="small" style={selected ? { color: '#fff' } : undefined}>{day}</ThemedText></TouchableOpacity>;
          })}
        </View>
      </View>}
    </View>
  );
}
const styles = StyleSheet.create({
  container: { gap: 8, width: '100%' },
  field: { flexDirection: 'row', justifyContent: 'space-between', padding: 16, minHeight: 52, borderWidth: 1, borderRadius: 14 },
  calendar: { padding: 10, borderRadius: 14 },
  navigation: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  arrow: { padding: 12 },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: { width: '14.2857%', minHeight: 42, alignItems: 'center', justifyContent: 'center', borderRadius: 10 },
  selected: { backgroundColor: '#4f46e5' },
});