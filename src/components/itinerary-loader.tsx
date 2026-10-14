import { useI18n } from '@/i18n';
import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Platform, StyleSheet, Text, View } from 'react-native';

const messages = [
  'Great adventures start with a little curiosity.',
  'Hidden streets. Local flavors. Your next favorite place.',
  'Less rushing around. More moments worth remembering.',
  'A little travel magic is on its way.',
];
const stops = Array.from({ length: 33 }, (_, index) => index / 32);
const orbitX = stops.map((step) => Math.cos(step * Math.PI * 2) * 108);
const orbitY = stops.map((step) => Math.sin(step * Math.PI * 2) * 68);

export function ItineraryLoader({ destination }: { destination: string }) {
  const { t } = useI18n();
  const [flight] = useState(() => new Animated.Value(0));
  const [drift] = useState(() => new Animated.Value(0));
  const [reveal] = useState(() => new Animated.Value(0));
  const [pulse] = useState(() => new Animated.Value(0));
  const [reduceMotion, setReduceMotion] = useState(true);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (mounted) setReduceMotion(enabled);
    }).catch(() => {});
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    const timer = setInterval(() => setMessageIndex((index) => (index + 1) % messages.length), 6000);
    return () => {
      mounted = false;
      subscription.remove();
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (reduceMotion) return;
    const animation = Animated.parallel([
      Animated.loop(Animated.timing(drift, {
        toValue: 1, duration: 10000, easing: Easing.linear,
        useNativeDriver: Platform.OS !== 'web', isInteraction: false,
      })),
      Animated.loop(Animated.timing(reveal, {
        toValue: 1, duration: 6000, easing: Easing.linear,
        useNativeDriver: Platform.OS !== 'web', isInteraction: false,
      })),
      Animated.loop(Animated.timing(flight, {
        toValue: 1, duration: 5000, easing: Easing.linear,
        useNativeDriver: Platform.OS !== 'web', isInteraction: false,
      })),
      Animated.loop(Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.quad), useNativeDriver: Platform.OS !== 'web', isInteraction: false }),
        Animated.timing(pulse, { toValue: 0, duration: 1200, easing: Easing.inOut(Easing.quad), useNativeDriver: Platform.OS !== 'web', isInteraction: false }),
      ])),
    ]);
    animation.start();
    return () => {
      animation.stop();
      flight.setValue(0);
      pulse.setValue(0);
      drift.setValue(0);
      reveal.setValue(0);
    };
  }, [drift, flight, pulse, reduceMotion, reveal]);

  return (
    <View style={styles.card} accessibilityLiveRegion="polite">
      <View style={styles.tag}><View style={styles.tagDot} /><Text style={styles.tagText} numberOfLines={1}>{t('NEXT STOP: {city}', { city: destination.toUpperCase() })}</Text></View>
      <View style={styles.scene} accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Animated.View style={[styles.halo, { opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.3, 0.65] }), transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] }) }] }]} />
        {[0, 1, 2].map((index) => (
          <Animated.View key={`cloud-${index}`} style={[styles.cloud, {
            top: 22 + index * 63,
            left: 0,
            opacity: reduceMotion ? 0.5 : drift.interpolate({ inputRange: [0, 0.15, 0.85, 1], outputRange: [0, 0.65, 0.65, 0] }),
            transform: [{ translateX: drift.interpolate({ inputRange: [0, 1], outputRange: index % 2 === 0 ? [-64, 270] : [270, -64] }) }],
          }]}><Text style={styles.cloudIcon}>☁</Text></Animated.View>
        ))}
        <View style={styles.orbit} />
        <Animated.View style={[styles.globe, { transform: [{ rotate: pulse.interpolate({ inputRange: [0, 1], outputRange: ['-7deg', '7deg'] }) }, { scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.04] }) }] }]}>
          <View style={styles.meridian} /><View style={[styles.meridian, styles.narrowMeridian]} />
          <View style={styles.equator} /><View style={[styles.equator, styles.upperLatitude]} /><View style={[styles.equator, styles.lowerLatitude]} />
          <View style={styles.landOne} /><View style={styles.landTwo} /><View style={styles.landThree} />
          <View style={styles.destination}><View style={styles.pinCore} /></View>
        </Animated.View>
        {[1, 2, 3, 4, 5, 6].map((index) => (
          <Animated.View key={`trail-${index}`} style={[styles.trail, {
            opacity: reduceMotion ? 0 : 0.7 - index * 0.09,
            transform: [
              { translateX: flight.interpolate({ inputRange: stops, outputRange: stops.map((step) => Math.cos((step - index * 0.018) * Math.PI * 2) * 108) }) },
              { translateY: flight.interpolate({ inputRange: stops, outputRange: stops.map((step) => Math.sin((step - index * 0.018) * Math.PI * 2) * 68) }) },
              { scale: 1 - index * 0.1 },
            ],
          }]} />
        ))}
        {Array.from({ length: 12 }, (_, index) => (
          <Animated.View key={`particle-${index}`} style={[styles.particle, {
            left: 128 + Math.cos(index * Math.PI / 6) * 110,
            top: 109 + Math.sin(index * Math.PI / 6) * 90,
            backgroundColor: ['#ffce73', '#8bf5dc', '#c0a1ff'][index % 3],
            opacity: reduceMotion ? 0.3 : pulse.interpolate({ inputRange: [0, 1], outputRange: index % 2 === 0 ? [0.2, 1] : [1, 0.2] }),
            transform: [{ translateY: pulse.interpolate({ inputRange: [0, 1], outputRange: [0, index % 2 === 0 ? -14 : 14] }) }, { scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.6, 1.4] }) }],
          }]} />
        ))}
        <Animated.View style={[styles.plane, { transform: [
          { translateX: flight.interpolate({ inputRange: stops, outputRange: orbitX }) },
          { translateY: flight.interpolate({ inputRange: stops, outputRange: orbitY }) },
          { rotate: flight.interpolate({ inputRange: [0, 1], outputRange: ['90deg', '450deg'] }) },
        ] }]}><Text style={styles.planeIcon}>✈︎</Text></Animated.View>
        {[{ icon: '📷', left: 5, top: 143 }, { icon: '🍕', left: 207, top: 146 }, { icon: '🏛️', left: 196, top: 17 }].map((item, index) => (
          <Animated.View key={item.icon} style={[styles.travelToken, { left: item.left, top: item.top, opacity: reduceMotion ? 1 : reveal.interpolate({ inputRange: [0, 0.12 + index * 0.1, 0.22 + index * 0.1, 0.85, 1], outputRange: [0, 0, 1, 1, 0] }), transform: [
            { scale: reduceMotion ? 1 : reveal.interpolate({ inputRange: [0, 0.12 + index * 0.1, 0.22 + index * 0.1, 0.32 + index * 0.1, 0.85, 1], outputRange: [0.3, 0.3, 1.2, 1, 1, 0.3] }) },
            { translateY: pulse.interpolate({ inputRange: [0, 1], outputRange: index % 2 === 0 ? [0, -9] : [-9, 0] }) },
            { rotate: pulse.interpolate({ inputRange: [0, 1], outputRange: index % 2 === 0 ? ['-8deg', '8deg'] : ['8deg', '-8deg'] }) },
          ] }]}><Text style={styles.tokenIcon}>{item.icon}</Text></Animated.View>
        ))}
        <Text style={[styles.spark, styles.sparkOne]}>✦</Text><Text style={[styles.spark, styles.sparkTwo]}>✧</Text>
      </View>
      <Text style={styles.title}>{t("Your adventure is taking shape")}</Text>
      <Animated.Text style={[styles.message, { opacity: reduceMotion ? 1 : reveal.interpolate({ inputRange: [0, 0.1, 0.9, 1], outputRange: [0, 1, 1, 0] }), transform: [{ translateY: reduceMotion ? 0 : reveal.interpolate({ inputRange: [0, 0.1, 0.9, 1], outputRange: [8, 0, 0, -8] }) }] }]}>{t(messages[messageIndex])}</Animated.Text>
      <View style={styles.footer}>
        <View style={styles.dots}>{[0, 1, 2].map((index) => <Animated.View key={index} style={[styles.dot, { opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: index === 1 ? [1, 0.35] : [0.35, 1] }) }]} />)}</View>
        <Text style={styles.footerText}>{t("Creating your itinerary. This may take a few minutes.")}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { width: '100%', alignItems: 'center', backgroundColor: '#13274a', borderRadius: 28, padding: 20, borderWidth: 1, borderColor: '#2b395a', overflow: 'hidden' },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, backgroundColor: '#1f2b46' },
  tagDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#85dfce' },
  tagText: { flexShrink: 1, fontSize: 10, fontWeight: '700', letterSpacing: 1.5, color: '#b7eadd' },
  scene: { width: 256, height: 258, alignItems: 'center', justifyContent: 'center', marginVertical: 12 },
  halo: { position: 'absolute', width: 190, height: 190, borderRadius: 95, backgroundColor: '#6254de' },
  orbit: { position: 'absolute', width: 216, height: 136, borderRadius: 108, borderWidth: 1, borderStyle: 'dashed', borderColor: '#7788b5' },
  globe: { width: 144, height: 144, borderRadius: 72, backgroundColor: '#238fcb', borderWidth: 1, borderColor: '#5b82a3', overflow: 'hidden' },
  meridian: { position: 'absolute', top: -1, left: 25, width: 92, height: 144, borderRadius: 72, borderWidth: 1, borderColor: '#3e5f81' },
  narrowMeridian: { left: 51, width: 40 },
  equator: { position: 'absolute', top: 70, width: 144, height: 1, backgroundColor: '#3e5f81' },
  upperLatitude: { top: 35 }, lowerLatitude: { top: 105 },
  landOne: { position: 'absolute', top: 24, left: 23, width: 50, height: 37, borderRadius: 15, backgroundColor: '#74e2aa', transform: [{ rotate: '-24deg' }] },
  landTwo: { position: 'absolute', top: 57, left: 53, width: 30, height: 56, borderRadius: 14, backgroundColor: '#74e2aa', transform: [{ rotate: '-20deg' }] },
  landThree: { position: 'absolute', top: 31, left: 100, width: 43, height: 60, borderRadius: 17, backgroundColor: '#39bf99', transform: [{ rotate: '28deg' }] },
  destination: { position: 'absolute', top: 34, left: 57, width: 22, height: 22, borderRadius: 11, backgroundColor: '#ffffff30', alignItems: 'center', justifyContent: 'center' },
  pinCore: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#ffe0a3' },
  trail: { position: 'absolute', width: 12, height: 12, borderRadius: 6, backgroundColor: '#ffe2a0' },
  particle: { position: 'absolute', width: 4, height: 4, borderRadius: 2 },
  plane: { position: 'absolute', width: 36, height: 36, borderRadius: 18, backgroundColor: '#ffd073', alignItems: 'center', justifyContent: 'center' },
  cloud: { position: 'absolute' },
  cloudIcon: { fontSize: 48, color: '#e3f4ff' },
  travelToken: { position: 'absolute', width: 39, height: 39, borderRadius: 13, backgroundColor: '#ffffff18', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#ffffff25' },
  tokenIcon: { fontSize: 24 },
  planeIcon: { fontSize: 25, lineHeight: 31, color: '#4f46e5' },
  spark: { position: 'absolute', color: '#e6c88e', fontSize: 18 },
  sparkOne: { top: 28, left: 26 }, sparkTwo: { bottom: 24, right: 24 },
  title: { fontSize: 23, lineHeight: 30, fontWeight: '700', color: '#f5f3ff', textAlign: 'center' },
  message: { minHeight: 56, marginTop: 12, maxWidth: 360, fontSize: 15, lineHeight: 23, color: '#b7c2dc', textAlign: 'center' },
  footer: { alignItems: 'center', gap: 12, marginTop: 20 },
  dots: { flexDirection: 'row', gap: 6 },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#b6a7f7' },
  footerText: { fontSize: 12, lineHeight: 18, textAlign: 'center', color: '#9aaacd' },
});
