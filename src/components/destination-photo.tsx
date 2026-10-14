import { useI18n } from '@/i18n';
import { Image } from 'expo-image';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Platform, ScrollView, StyleSheet, TouchableOpacity, useWindowDimensions, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';

type Photo = { url: string; title: string; artist: string; license: string; source_url: string };
type Result = { destination: string; photos: Photo[]; error?: string };

function PhotoCard({ photo, width }: { photo: Photo; width: number }) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  return (
    <ThemedView type="backgroundElement" style={[styles.card, { width }]}>
      {failed ? (
        <View style={[styles.image, styles.placeholder]}>
          <ThemedText type="small" style={styles.placeholderText}>{t("This photo could not load.")}</ThemedText>
          <TouchableOpacity accessibilityRole="button" onPress={() => { setFailed(false); setAttempt((value) => value + 1); }}>
            <ThemedText style={styles.link}>{t("Retry photo ↻")}</ThemedText>
          </TouchableOpacity>
        </View>
      ) : <Image key={attempt} source={{ uri: photo.url }} style={styles.image} contentFit="cover" transition={300}
          cachePolicy={attempt ? 'none' : 'memory-disk'} accessibilityLabel={photo.title}
          onError={(event) => { console.warn('Destination image failed:', event.error); setFailed(true); }} />}
      <View style={styles.caption}>
        <ThemedText type="smallBold" numberOfLines={2}>{photo.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{photo.artist} · {photo.license}</ThemedText>
        <TouchableOpacity accessibilityRole="link" onPress={() => { void Linking.openURL(photo.source_url).catch(() => {}); }}>
          <ThemedText style={styles.link}>{t("Source & license ↗")}</ThemedText>
        </TouchableOpacity>
      </View>
    </ThemedView>
  );
}

export function DestinationGallery({ destination }: { destination: string }) {
  const { t } = useI18n();
  const { width } = useWindowDimensions();
  const [result, setResult] = useState<Result | null>(null);
  const [retry, setRetry] = useState(0);
  const current = result?.destination === destination ? result : null;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const load = async () => {
      try {
        const baseUrl = process.env.EXPO_PUBLIC_API_URL || (Platform.OS === 'web'
          ? 'http://localhost:5000' : 'http://192.168.100.42:5000');
        const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/destination-photos?destination=${encodeURIComponent(destination)}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Photos are unavailable right now.');
        if (active) setResult({ destination, photos: data.photos ?? [] });
      } catch {
        if (active) setResult({ destination, photos: [], error: 'Could not load destination photos. Your itinerary is still ready below.' });
      } finally {
        clearTimeout(timeout);
      }
    };
    void load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [destination, retry]);

  return (
    <View style={styles.gallery}>
      <ThemedText style={styles.heading}>{t('A glimpse of {city}', { city: destination.split(',')[0] })}</ThemedText>
      {!current && <View style={styles.loading}><ActivityIndicator color="#8174ed" /><ThemedText type="small">{t("Loading destination photos...")}</ThemedText></View>}
      {current?.photos.length ? (
        <>
          <ThemedText type="small" themeColor="textSecondary">{t("Swipe through the destination gallery")}</ThemedText>
          <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={styles.photos} keyboardShouldPersistTaps="handled">
            {current.photos.map((photo) => <PhotoCard key={photo.url} photo={photo} width={Math.max(180, Math.min(320, width - 112))} />)}
          </ScrollView>
        </>
      ) : current && <View style={styles.loading}>
          <ThemedText type="small" themeColor="textSecondary">{t(current.error || 'No destination photos are available yet.')}</ThemedText>
          <TouchableOpacity accessibilityRole="button" onPress={() => { setResult(null); setRetry((value) => value + 1); }}><ThemedText style={styles.link}>{t("Retry gallery ↻")}</ThemedText></TouchableOpacity>
        </View>}
    </View>
  );
}

const styles = StyleSheet.create({
  gallery: { width: '100%', gap: 12, marginVertical: 12 },
  heading: { fontSize: 21, lineHeight: 29, fontWeight: '700' },
  loading: { gap: 12, paddingVertical: 16 },
  photos: { gap: 14, paddingBottom: 10 },
  card: { borderRadius: 18, overflow: 'hidden' },
  image: { width: '100%', aspectRatio: 4 / 3 },
  placeholder: { backgroundColor: '#172b49', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 16 },
  placeholderText: { color: '#d1dbed', textAlign: 'center' },
  caption: { padding: 14, gap: 8 },
  link: { color: '#8174ed', fontSize: 13 },
});