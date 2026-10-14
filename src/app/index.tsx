import { LanguageSwitcher } from '@/components/language-switcher';
import { useI18n } from '@/i18n';
import { useEffect, useRef, useState } from 'react';
import { Keyboard, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { DepartureDatePicker, localDate } from '@/components/departure-date-picker';
import { CityAutocomplete } from '@/components/city-autocomplete';
import { DestinationGallery } from '@/components/destination-photo';
import { ItineraryContent } from '@/components/itinerary-content';
import { ItineraryLoader } from '@/components/itinerary-loader';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';


const suggestedDestinations = ['Rome, Italy', 'Paris, France', 'Barcelona, Spain', 'Tokyo, Japan'];

export default function HomeScreen() {
  const { t, language, formatDate, formatBudget } = useI18n();
  const theme = useTheme();

  const scrollRef = useRef<ScrollView>(null);
  const pendingLoaderScroll = useRef(false);
  const formPositions = useRef({ route: 0, calendar: 0, settings: 0, budget: 0, days: 0 });
  const focusedNumberField = useRef<'budget' | 'days' | null>(null);

  const revealNumberField = () => {
    const field = focusedNumberField.current;
    if (!field || Platform.OS === 'web') return;
    const positions = formPositions.current;
    scrollRef.current?.scrollTo({ y: Math.max(0, positions.route + positions.settings + positions[field] - Spacing.three), animated: true });
  };

  useEffect(() => {
    const subscription = Keyboard.addListener('keyboardDidShow', () => {
      const field = focusedNumberField.current;
      if (!field) return;
      const positions = formPositions.current;
      scrollRef.current?.scrollTo({ y: Math.max(0, positions.route + positions.settings + positions[field] - Spacing.three), animated: true });
    });
    return () => subscription.remove();
  }, []);
  const [origin, setOrigin] = useState('Bucharest, Romania');
  const [destination, setDestination] = useState('Rome, Italy');
  const [budget, setBudget] = useState('300');
  const [days, setDays] = useState('3');
  const [departureDate, setDepartureDate] = useState(() => { const date = new Date(); date.setDate(date.getDate() + 1); return localDate(date); });
  const [loading, setLoading] = useState(false);
  const [itineraryText, setItineraryText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resultRoute, setResultRoute] = useState<{ origin: string; destination: string; budget: number; days: number; departureDate: string; endDate: string } | null>(null);

  const changeCity = (field: 'origin' | 'destination', value: string) => {
    if (field === 'origin') setOrigin(value);
    else setDestination(value);
    setItineraryText(null);
    setResultRoute(null);
    setError(null);
  };

  const handleFetchItinerary = async () => {
    if (loading) return;
    const departure = origin.trim();
    const arrival = destination.trim();
    if (departure.length < 2 || arrival.length < 2) {
      setError('Please enter both your departure city and destination.');
      return;
    }
    if (departure.toLowerCase() === arrival.toLowerCase()) {
      setError('Choose a destination different from your departure city.');
      return;
    }
    const normalizedBudget = budget.trim().replace(',', '.');
    const tripDays = Number(days.trim());
    if (!/^\d{1,6}(\.\d{1,2})?$/.test(normalizedBudget) || Number(normalizedBudget) < 1 || Number(normalizedBudget) > 100000) {
      setError('Enter a total budget between EUR 1 and EUR 100,000, with up to two decimal places.');
      return;
    }
    if (!/^\d{1,2}$/.test(days.trim()) || tripDays < 1 || tripDays > 30) {
      setError('Choose a whole number of days between 1 and 30.');
      return;
    }
    Keyboard.dismiss();
    pendingLoaderScroll.current = true;
    setLoading(true);
    setError(null);
    setItineraryText(null);
    setResultRoute(null);
    try {
      const baseUrl = process.env.EXPO_PUBLIC_API_URL || (Platform.OS === 'web'
        ? 'http://localhost:5000'
        : 'http://192.168.100.42:5000');
      const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/itinerary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ origin: departure, destination: arrival, budget: normalizedBudget, days: tripDays, departure_date: departureDate, language }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not create your itinerary. Please try again.');
      if (typeof data.text_itinerary !== 'string' || !data.text_itinerary.trim()) {
        throw new Error('The travel service returned an empty itinerary. Please try again.');
      }
      setResultRoute({ origin: data.origin || departure, destination: data.destination || arrival, budget: Number(data.budget ?? normalizedBudget), days: data.days ?? tripDays, departureDate: data.departure_date || departureDate, endDate: data.end_date });
      setItineraryText(data.text_itinerary);
    } catch (failure) {
      setError(failure instanceof TypeError
        ? 'Could not connect to the travel service. Please check that the backend is running.'
        : failure instanceof Error ? failure.message : 'Something went wrong. Please try again.');
    } finally {
      pendingLoaderScroll.current = false;
      setLoading(false);
    }
  };

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView style={styles.keyboardArea} enabled={Platform.OS !== 'web'} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView ref={scrollRef} onLayout={revealNumberField} keyboardDismissMode="on-drag" contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <LanguageSwitcher disabled={loading} onChange={() => { setItineraryText(null); setResultRoute(null); setError(null); }} />
          <ThemedView style={styles.heroSection}>
            <ThemedText type="title" style={styles.title}>Ghost Travel Agent</ThemedText>
            <ThemedText themeColor="textSecondary" style={styles.subtitle}>{t("Where will your next adventure take you?")}</ThemedText>
          </ThemedView>

          <ThemedView type="backgroundElement" style={styles.routeCard} onLayout={(event) => { formPositions.current.route = event.nativeEvent.layout.y; }}>
            <ThemedText type="smallBold">{t("FROM")}</ThemedText>
            <CityAutocomplete label={t("Departure city")} value={origin} onChange={(value) => changeCity('origin', value)} disabled={loading} />
            <TouchableOpacity accessibilityRole="button" accessibilityLabel={t("Swap departure and destination")} disabled={loading}
              style={styles.swapButton} onPress={() => {
                setOrigin(destination); setDestination(origin); setItineraryText(null); setResultRoute(null); setError(null);
              }}><ThemedText style={styles.swapText}>{t("⇅ Swap cities")}</ThemedText></TouchableOpacity>
            <ThemedText type="smallBold">{t("TO")}</ThemedText>
            <CityAutocomplete label={t("Destination city")} value={destination} onChange={(value) => changeCity('destination', value)} disabled={loading} />
            <ThemedText type="small" themeColor="textSecondary">{t("Pick an idea or enter any city above")}</ThemedText>
            <ThemedView type="backgroundElement" style={styles.chips}>
              {suggestedDestinations.map((city) => (
                <TouchableOpacity key={city} accessibilityRole="button" accessibilityState={{ selected: destination === city }}
                  disabled={loading} onPress={() => changeCity('destination', city)}
                  style={[styles.chip, { borderColor: '#8174ed55' }, destination === city && styles.selectedChip]}>
                  <ThemedText type="small" style={destination === city ? styles.selectedChipText : undefined}>{city.split(',')[0]}</ThemedText>
                </TouchableOpacity>
              ))}
            </ThemedView>
            <View style={styles.calendarContainer} onLayout={(event) => { formPositions.current.calendar = event.nativeEvent.layout.y; }}>
            <DepartureDatePicker onCalendarLayout={() => {
              scrollRef.current?.scrollTo({ y: Math.max(0, formPositions.current.route + formPositions.current.calendar - Spacing.three), animated: true });
            }} value={departureDate} disabled={loading} onChange={(value) => {
              setDepartureDate(value); setItineraryText(null); setResultRoute(null); setError(null);
            }} />
            </View>
            <View style={styles.tripSettings} onLayout={(event) => { formPositions.current.settings = event.nativeEvent.layout.y; }}>
              <View style={styles.settingField} onLayout={(event) => { formPositions.current.budget = event.nativeEvent.layout.y; }}>
                <ThemedText type="smallBold">{t("TOTAL BUDGET (EUR)")}</ThemedText>
                <TextInput accessibilityLabel={t("Total trip budget in EUR")} value={budget} onFocus={() => { focusedNumberField.current = 'budget'; revealNumberField(); }} onBlur={() => { focusedNumberField.current = null; }}
                  onChangeText={(value) => { setBudget(value); setItineraryText(null); setResultRoute(null); setError(null); }}
                  editable={!loading} keyboardType="decimal-pad" placeholder="300" maxLength={9}
                  placeholderTextColor={theme.textSecondary}
                  style={[styles.numberInput, { color: theme.text, backgroundColor: theme.background, borderColor: theme.backgroundSelected }]} />
              </View>
              <View style={styles.settingField} onLayout={(event) => { formPositions.current.days = event.nativeEvent.layout.y; }}>
                <ThemedText type="smallBold">{t("NUMBER OF DAYS")}</ThemedText>
                <TextInput accessibilityLabel={t("Number of days")} value={days} onFocus={() => { focusedNumberField.current = 'days'; revealNumberField(); }} onBlur={() => { focusedNumberField.current = null; }}
                  onChangeText={(value) => { setDays(value); setItineraryText(null); setResultRoute(null); setError(null); }}
                  editable={!loading} keyboardType="number-pad" placeholder="3" maxLength={2}
                  placeholderTextColor={theme.textSecondary}
                  style={[styles.numberInput, { color: theme.text, backgroundColor: theme.background, borderColor: theme.backgroundSelected }]} />
              </View>
            </View>
            <ThemedText type="small" themeColor="textSecondary">{t("Budget covers the whole trip: flights, stays, food, and activities. Choose 1–30 days.")}</ThemedText>
          </ThemedView>

          {error && <ThemedText accessibilityRole="alert" style={styles.error}>{t(error)}</ThemedText>}
          <TouchableOpacity accessibilityRole="button" style={[styles.aiButton, loading && styles.disabledButton]}
            onPress={handleFetchItinerary} disabled={loading}>
            <ThemedText style={styles.buttonText}>{t(loading ? 'Planning your adventure...' : 'Create my itinerary')}</ThemedText>
          </TouchableOpacity>
          {loading && (
            <View style={styles.loaderContainer} onLayout={(event) => {
              if (!pendingLoaderScroll.current) return;
              pendingLoaderScroll.current = false;
              scrollRef.current?.scrollTo({ y: Math.max(0, event.nativeEvent.layout.y - Spacing.three), animated: true });
            }}>
              <ItineraryLoader destination={destination.trim()} />
            </View>
          )}
          {itineraryText && (
            <ThemedView type="backgroundElement" style={styles.resultCard}>
              <ThemedText type="small" themeColor="textSecondary">{resultRoute?.origin} → {resultRoute?.destination}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">{t(resultRoute?.days === 1 ? '{count} day · {budget} total budget' : '{count} days · {budget} total budget', { count: resultRoute?.days ?? 0, budget: formatBudget(resultRoute?.budget ?? 0) })}</ThemedText>
              <ThemedText type="subtitle" style={styles.resultTitle}>{t("Your travel itinerary")}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">{formatDate(resultRoute?.departureDate)} → {formatDate(resultRoute?.endDate)}</ThemedText>
              <DestinationGallery key={'gallery:' + itineraryText} destination={resultRoute?.destination || destination} />
              <ItineraryContent key={'itinerary:' + itineraryText} text={itineraryText} />
            </ThemedView>
          )}
        </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', flexDirection: 'row' },
  keyboardArea: { flex: 1 },
  calendarContainer: { width: '100%', paddingTop: 16 },
  safeArea: { flex: 1, maxWidth: MaxContentWidth },
  scrollContent: { paddingHorizontal: Spacing.four, alignItems: 'center', gap: Spacing.three, paddingBottom: Spacing.four },
  heroSection: { alignItems: 'center', paddingVertical: Spacing.four, gap: Spacing.two },
  title: { textAlign: 'center', fontSize: 34, lineHeight: 42 },
  subtitle: { textAlign: 'center' },
  routeCard: { width: '100%', padding: 20, borderRadius: 24, gap: 12 },
  tripSettings: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginTop: 8 },
  settingField: { flex: 1, minWidth: 120, gap: 8 },
  numberInput: { minHeight: 52, paddingHorizontal: 16, paddingVertical: 12, fontSize: 17, borderRadius: 14, borderWidth: 1 },
  swapButton: { alignSelf: 'flex-end', paddingVertical: 8, paddingHorizontal: 12 },
  swapText: { color: '#8174ed', fontSize: 14 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  selectedChip: { backgroundColor: '#4f46e5', borderColor: '#4f46e5' },
  selectedChipText: { color: '#fff' },
  aiButton: { backgroundColor: '#4f46e5', paddingVertical: 16, paddingHorizontal: 24, borderRadius: 16, width: '100%', alignItems: 'center' },
  loaderContainer: { width: '100%' },
  disabledButton: { opacity: 0.7 },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  error: { color: '#e05252', width: '100%', fontSize: 14 },
  resultCard: { width: '100%', padding: Spacing.four, borderRadius: Spacing.four, gap: Spacing.two, borderWidth: 1, borderColor: 'rgba(148, 163, 184, 0.2)' },
  resultTitle: { fontWeight: 'bold', fontSize: 26 },
});
