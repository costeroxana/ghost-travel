import { useI18n } from '@/i18n';
import { useEffect, useRef, useState } from 'react';
import { Keyboard, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';

// Local suggestions keep typing responsive without a service key or network request.
const cities = [
  'Bucharest, Romania', 'Cluj-Napoca, Romania', 'Timișoara, Romania', 'Iași, Romania',
  'Brașov, Romania', 'Sibiu, Romania', 'Oradea, Romania', 'Constanța, Romania',
  'Craiova, Romania', 'Suceava, Romania', 'Bacău, Romania', 'Târgu Mureș, Romania',
  'Rome, Italy', 'Milan, Italy', 'Florence, Italy', 'Venice, Italy', 'Naples, Italy', 'Bologna, Italy',
  'Paris, France', 'Nice, France', 'Lyon, France', 'Marseille, France',
  'Barcelona, Spain', 'Madrid, Spain', 'Valencia, Spain', 'Seville, Spain', 'Malaga, Spain',
  'Lisbon, Portugal', 'Porto, Portugal', 'Athens, Greece', 'Thessaloniki, Greece',
  'London, United Kingdom', 'Edinburgh, United Kingdom', 'Manchester, United Kingdom',
  'Dublin, Ireland', 'Amsterdam, Netherlands', 'Rotterdam, Netherlands',
  'Brussels, Belgium', 'Berlin, Germany', 'Munich, Germany', 'Frankfurt, Germany', 'Hamburg, Germany',
  'Vienna, Austria', 'Salzburg, Austria', 'Prague, Czechia', 'Budapest, Hungary',
  'Warsaw, Poland', 'Krakow, Poland', 'Copenhagen, Denmark', 'Stockholm, Sweden',
  'Oslo, Norway', 'Helsinki, Finland', 'Reykjavik, Iceland',
  'Zurich, Switzerland', 'Geneva, Switzerland', 'Zagreb, Croatia', 'Dubrovnik, Croatia',
  'Split, Croatia', 'Ljubljana, Slovenia', 'Belgrade, Serbia', 'Sofia, Bulgaria', 'Istanbul, Türkiye',
  'Antalya, Türkiye', 'Dubai, United Arab Emirates', 'Abu Dhabi, United Arab Emirates',
  'Cairo, Egypt', 'Marrakesh, Morocco', 'Cape Town, South Africa', 'Nairobi, Kenya',
  'Tokyo, Japan', 'Kyoto, Japan', 'Osaka, Japan', 'Seoul, South Korea',
  'Bangkok, Thailand', 'Singapore, Singapore', 'Kuala Lumpur, Malaysia', 'Hanoi, Vietnam',
  'Beijing, China', 'Shanghai, China', 'Hong Kong, China', 'Delhi, India', 'Mumbai, India',
  'New York, United States', 'Los Angeles, United States', 'San Francisco, United States',
  'Chicago, United States', 'Miami, United States', 'Boston, United States',
  'Toronto, Canada', 'Vancouver, Canada', 'Montreal, Canada', 'Mexico City, Mexico',
  'Cancun, Mexico', 'Rio de Janeiro, Brazil', 'São Paulo, Brazil', 'Buenos Aires, Argentina',
  'Lima, Peru', 'Bogotá, Colombia', 'Santiago, Chile',
  'Sydney, Australia', 'Melbourne, Australia', 'Auckland, New Zealand',
];

function normalize(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

type Props = { label: string; value: string; onChange: (city: string) => void; disabled?: boolean };

export function CityAutocomplete({ label, value, onChange, disabled = false }: Props) {
  const { t } = useI18n();
  const theme = useTheme();
  const inputRef = useRef<TextInput>(null);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const query = normalize(value);
  const matches = cities.filter((city) => query.split(/\s+/).every((word) => normalize(city).includes(word)))
    .sort((a, b) => Number(normalize(b).startsWith(query)) - Number(normalize(a).startsWith(query)))
    .slice(0, 6);

  useEffect(() => () => {
    if (blurTimer.current) clearTimeout(blurTimer.current);
  }, []);

  const choose = (city: string) => {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    onChange(city);
    setOpen(false);
    setActiveIndex(-1);
    inputRef.current?.blur();
    Keyboard.dismiss();
  };

  return (
    <View style={styles.container}>
      <View style={[styles.inputRow, { backgroundColor: theme.background, borderColor: open ? '#8174ed' : theme.backgroundSelected }]}>
        <TextInput ref={inputRef} accessibilityLabel={label} value={value}
          onChangeText={(text) => { onChange(text); setOpen(true); setActiveIndex(-1); }}
          onFocus={() => { if (blurTimer.current) clearTimeout(blurTimer.current); setOpen(true); setActiveIndex(-1); }}
          onBlur={() => { blurTimer.current = setTimeout(() => setOpen(false), 180); }}
          onKeyPress={(event) => {
            if (event.nativeEvent.key === 'Escape') { setOpen(false); return; }
            if (event.nativeEvent.key === 'ArrowDown' || event.nativeEvent.key === 'ArrowUp') {
              event.preventDefault();
              setOpen(true);
              if (matches.length) setActiveIndex((index) => event.nativeEvent.key === 'ArrowDown'
                ? (index + 1) % matches.length : (index <= 0 ? matches.length - 1 : index - 1));
            }
            if (event.nativeEvent.key === 'Enter' && open && activeIndex >= 0 && matches[activeIndex]) {
              event.preventDefault(); choose(matches[activeIndex]);
            }
          }}
          editable={!disabled} placeholder={t("Type a city or country")} placeholderTextColor={theme.textSecondary}
          maxLength={100} autoCapitalize="words" autoCorrect={false}
          style={[styles.input, { color: theme.text }]} />
        <TouchableOpacity accessibilityRole="button" accessibilityLabel={t('Show suggestions for {field}', { field: label })}
          disabled={disabled} style={styles.toggle} onPress={() => {
            if (open) { setOpen(false); inputRef.current?.blur(); }
            else inputRef.current?.focus();
          }}><ThemedText themeColor="textSecondary">{open ? '▴' : '▾'}</ThemedText></TouchableOpacity>
      </View>
      {open && !disabled && (
        <View style={[styles.dropdown, { backgroundColor: theme.background, borderColor: theme.backgroundSelected }]}>
          {matches.length ? matches.map((city, index) => (
            <TouchableOpacity key={city} accessibilityRole="button" accessibilityLabel={t('Select {city}', { city })}
              onPress={() => choose(city)} style={[styles.option, index === activeIndex && { backgroundColor: theme.backgroundSelected }]}>
              <ThemedText style={styles.pin}>↗</ThemedText>
              <View style={styles.optionText}>
                <ThemedText type="smallBold">{city.split(',')[0]}</ThemedText>
                <ThemedText type="small" themeColor="textSecondary">{city.split(',').slice(1).join(',').trim()}</ThemedText>
              </View>
            </TouchableOpacity>
          )) : <ThemedText type="small" themeColor="textSecondary" style={styles.empty}>{t("No suggestions found. You can still use the city you typed.")}</ThemedText>}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%', gap: 6 },
  inputRow: { flexDirection: 'row', alignItems: 'center', borderRadius: 14, borderWidth: 1 },
  input: { flex: 1, minWidth: 0, minHeight: 52, paddingHorizontal: 16, paddingVertical: 12, fontSize: 17 },
  toggle: { width: 44, minHeight: 52, alignItems: 'center', justifyContent: 'center' },
  dropdown: { borderWidth: 1, borderRadius: 14, overflow: 'hidden' },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 16 },
  pin: { color: '#8174ed', fontSize: 20 },
  optionText: { flex: 1 },
  empty: { padding: 16 },
});
