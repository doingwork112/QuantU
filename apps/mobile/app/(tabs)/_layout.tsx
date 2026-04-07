import { Tabs } from 'expo-router';
import { Text } from 'react-native';

const tab = (icon: string, label: string) => ({
  tabBarIcon: ({ focused }: { focused: boolean }) => (
    <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.5 }}>{icon}</Text>
  ),
  tabBarLabel: label,
});

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0F0D2E',
          borderTopColor: 'rgba(99,102,241,0.15)',
          height: 88,
          paddingBottom: 28,
          paddingTop: 8,
        },
        tabBarActiveTintColor: '#6366F1',
        tabBarInactiveTintColor: '#64748B',
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen name="score" options={tab('📊', '评分')} />
      <Tabs.Screen name="discover" options={tab('💘', '发现')} />
      <Tabs.Screen name="profile" options={tab('👤', '我的')} />
    </Tabs>
  );
}
