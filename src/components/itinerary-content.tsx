import { useI18n } from '@/i18n';
import { useState } from 'react';
import { Linking, StyleSheet, TouchableOpacity, View } from 'react-native';
import Markdown from 'react-native-markdown-display';

import { ThemedText } from '@/components/themed-text';
import { useTheme } from '@/hooks/use-theme';

export function ItineraryContent({ text }: { text: string }) {
  const { t } = useI18n();
  const theme = useTheme();
  const markdown = text.trim().replace(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n```$/, '$1');
  const sections = markdown.split(/(?=^##\s+)/m).filter((section) => section.trim());
  const dayIndices = sections.flatMap((section, index) => /^##\s+[^\w\n]*(?:Day|Ziua|Día|Jour|Tag|Giorno)\s+\d+\b/i.test(section) ? [index] : []);
  const firstDay = dayIndices[0];
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set(firstDay !== undefined ? [firstDay] : []));
  const markdownStyles = {
    body: { color: theme.text, fontSize: 16, lineHeight: 26 },
    heading1: { color: theme.text, fontSize: 26, lineHeight: 34, fontWeight: '700' as const, marginBottom: 16, marginTop: 8 },
    heading2: { color: theme.text, fontSize: 22, lineHeight: 30, fontWeight: '700' as const, marginBottom: 14, marginTop: 4 },
    heading3: { color: '#8174ed', fontSize: 17, lineHeight: 25, fontWeight: '700' as const, marginTop: 20, marginBottom: 8 },
    heading4: { color: theme.text, fontSize: 16, fontWeight: '700' as const, marginTop: 16, marginBottom: 8 },
    paragraph: { marginTop: 0, marginBottom: 14 },
    strong: { fontWeight: '700' as const },
    bullet_list: { marginBottom: 12 },
    ordered_list: { marginBottom: 12 },
    list_item: { marginBottom: 8 },
    bullet_list_icon: { color: '#8174ed', marginRight: 10, fontSize: 16, lineHeight: 26 },
    blockquote: { backgroundColor: theme.backgroundElement, borderLeftColor: '#8174ed', borderLeftWidth: 3, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 16 },
    hr: { backgroundColor: theme.backgroundSelected, height: 1, marginVertical: 20 },
    link: { color: '#8174ed', textDecorationLine: 'underline' as const },
    table: { borderColor: theme.backgroundSelected, borderWidth: 1, borderRadius: 8, marginBottom: 16 },
    th: { padding: 8, backgroundColor: theme.backgroundElement },
    td: { padding: 8 },
    tr: { borderBottomColor: theme.backgroundSelected },
    code_inline: { color: theme.text, backgroundColor: theme.backgroundElement },
    fence: { color: theme.text, backgroundColor: theme.backgroundElement, padding: 12 },
  };

  return (
    <View style={styles.sections}>
      {sections.map((section, index) => {
        const heading = section.match(/^##\s+(.+)(?:\r?\n|$)/);
        const title = heading ? heading[1].replace(/\*\*|__|`/g, '').replace(/\s+#+\s*$/, '').trim() : t('Trip overview');
        const body = heading ? section.slice(heading[0].length).trim() : section;
        const day = title.match(/(?:^|\s)((?:Day|Ziua|Día|Jour|Tag|Giorno)\s+\d+)\b/i)?.[1];
        const isExpanded = !day || expanded.has(index);
        const Header = day ? TouchableOpacity : View;
        return (
          <View key={index} style={[styles.section, { backgroundColor: theme.background, borderColor: theme.backgroundSelected }, day && styles.daySection]}>
            <Header accessibilityRole={day ? 'button' : undefined} accessibilityLabel={title} accessibilityState={day ? { expanded: isExpanded } : undefined}
              style={styles.sectionHeader} onPress={day ? () => setExpanded((previous) => {
                const next = new Set(previous);
                if (next.has(index)) next.delete(index);
                else next.add(index);
                return next;
              }) : undefined}>
              <View style={styles.headingContent}>
                {day && <View style={styles.dayBadge}><ThemedText style={styles.dayBadgeText}>{day.toUpperCase()}</ThemedText></View>}
                <ThemedText style={styles.sectionTitle}>{title}</ThemedText>
              </View>
              {day && <ThemedText style={styles.dayArrow} accessible={false}>{isExpanded ? '▾' : '▸'}</ThemedText>}
            </Header>
            {isExpanded && <View style={styles.sectionBody}>
              <Markdown style={markdownStyles} rules={{ image: () => null }} onLinkPress={(url) => {
                if (/^https?:\/\//i.test(url)) void Linking.openURL(url).catch(() => {});
                return false;
              }}>{body}</Markdown>
            </View>}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  dayArrow: { color: '#8174ed', fontSize: 20, lineHeight: 28 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, minHeight: 44 },
  headingContent: { flex: 1 },
  sectionTitle: { fontSize: 19, lineHeight: 27, fontWeight: '700' },
  sectionBody: { marginTop: 16 },
  sections: { width: '100%', gap: 16 },
  section: { borderWidth: 1, borderRadius: 18, padding: 16 },
  daySection: { borderLeftWidth: 4, borderLeftColor: '#8174ed' },
  dayBadge: { alignSelf: 'flex-start', backgroundColor: '#4f46e5', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, marginBottom: 12 },
  dayBadgeText: { color: '#fff', fontSize: 11, lineHeight: 17, fontWeight: '700', letterSpacing: 1 },
});