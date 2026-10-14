import { useRef, useState } from 'react';
import { Keyboard, Modal, ScrollView, StyleSheet, TouchableOpacity, useWindowDimensions, View } from 'react-native';
import { languages, useI18n } from '@/i18n';
import { ThemedText } from './themed-text';
import { useTheme } from '@/hooks/use-theme';

export function LanguageSwitcher({ disabled, onChange }: { disabled: boolean; onChange: () => void }) {
  const { language, setLanguage, t } = useI18n();
  const theme = useTheme();
  const { width, height } = useWindowDimensions();
  const anchor = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 60, left: 16 });
  const menuWidth = Math.min(220, width - 32);

  const showMenu = () => {
    Keyboard.dismiss();
    anchor.current?.measureInWindow((x, y, anchorWidth, anchorHeight) => {
      setPosition({
        top: Math.max(16, Math.min(y + anchorHeight + 6, height - 320)),
        left: Math.max(16, Math.min(x + anchorWidth - menuWidth, width - menuWidth - 16)),
      });
      setOpen(true);
    });
  };

  return <View ref={anchor} collapsable={false} style={styles.container}>
    <TouchableOpacity accessibilityRole="button" accessibilityLabel={t('Choose language')} accessibilityState={{ expanded: open }}
      disabled={disabled} onPress={showMenu} style={[styles.button, { backgroundColor: theme.backgroundElement }]}>
      <ThemedText type="small">◎ {t('Language')} · {languages.find((item) => item.code === language)?.name} ▾</ThemedText>
    </TouchableOpacity>
    <Modal visible={open && !disabled} transparent animationType="fade" statusBarTranslucent onRequestClose={() => setOpen(false)}>
      <View style={styles.overlay}>
        <TouchableOpacity style={StyleSheet.absoluteFill} accessibilityRole="button" accessibilityLabel={t('Close language menu')}
          activeOpacity={1} onPress={() => setOpen(false)} />
        <View style={[styles.options, { backgroundColor: theme.backgroundElement, top: position.top, left: position.left, width: menuWidth }]}>
          <ScrollView keyboardShouldPersistTaps="handled" style={{ maxHeight: Math.max(80, height - position.top - 16) }}>
            {languages.map((item) => <TouchableOpacity key={item.code} accessibilityRole="button" accessibilityState={{ selected: language === item.code }}
              style={styles.option} onPress={() => { if (item.code !== language) { setLanguage(item.code); onChange(); } setOpen(false); }}>
              <ThemedText type="small" style={language === item.code ? { color: '#8174ed', fontWeight: '700' } : undefined}>{item.name}{language === item.code ? ' ✓' : ''}</ThemedText>
            </TouchableOpacity>)}
          </ScrollView>
        </View>
      </View>
    </Modal>
  </View>;
}
const styles = StyleSheet.create({
  container: { alignSelf: 'flex-end', marginTop: 8 },
  button: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18 },
  overlay: { flex: 1 },
  options: { position: 'absolute', borderRadius: 14, padding: 4, elevation: 12, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 12, shadowOffset: { width: 0, height: 5 } },
  option: { paddingHorizontal: 14, paddingVertical: 12, minHeight: 44 },
});