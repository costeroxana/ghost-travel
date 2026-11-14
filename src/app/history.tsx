import { Stack } from "expo-router";
import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ItineraryContent } from "@/components/itinerary-content";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { apiBaseUrl } from "@/constants/api";
import { MaxContentWidth, Spacing } from "@/constants/theme";
import { useI18n } from "@/i18n";

type HistoryTrip = {
  id: string;
  origin?: string;
  destination?: string;
  departure_date?: string;
  created_at: number;
  text_itinerary: string;
};

export default function HistoryScreen() {
  const { t } = useI18n();
  const [trips, setTrips] = useState<HistoryTrip[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<HistoryTrip | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/itinerary/history`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (!Array.isArray(data?.trips)) throw new Error();
        if (!controller.signal.aborted) setTrips(data.trips);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void load();
    return () => controller.abort();
  }, []);

  return (
    <ThemedView style={styles.page}>
      <Stack.Screen options={{ headerShown: true, title: t("Search history") }} />
      <SafeAreaView edges={["bottom"]} style={styles.page}>
        <ScrollView contentContainerStyle={styles.content}>
          {selected ? (
            <>
              <TouchableOpacity accessibilityRole="button" onPress={() => setSelected(null)}>
                <ThemedText>{t("Back to history")}</ThemedText>
              </TouchableOpacity>
              <ThemedText type="title">{selected.destination ?? t("Cached itinerary")}</ThemedText>
              <ItineraryContent key={selected.id} text={selected.text_itinerary} />
            </>
          ) : failed ? (
            <ThemedText>{t("Could not load search history.")}</ThemedText>
          ) : trips === null ? (
            <ThemedText>{t("Loading search history…")}</ThemedText>
          ) : trips.length === 0 ? (
            <ThemedText>{t("No itineraries from the last 24 hours.")}</ThemedText>
          ) : trips.map((trip) => (
            <TouchableOpacity
              accessibilityRole="button"
              key={trip.id}
              onPress={() => setSelected(trip)}
              style={styles.trip}
            >
              {trip.origin && trip.destination ? (
                <ThemedText numberOfLines={1}>{trip.origin} → {trip.destination}</ThemedText>
              ) : (
                <ThemedText>{t("Cached itinerary")}</ThemedText>
              )}
              <ThemedText themeColor="textSecondary">
                {trip.departure_date ?? new Date(trip.created_at * 1000).toLocaleString()}
              </ThemedText>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
  trip: { gap: Spacing.two, paddingVertical: Spacing.two },
  content: {
    width: "100%",
    maxWidth: MaxContentWidth,
    alignSelf: "center",
    padding: Spacing.four,
    gap: Spacing.four,
  },
});
