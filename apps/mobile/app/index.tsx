import { Redirect } from 'expo-router';
import { useStore } from '../store';

export default function Index() {
  const user = useStore((s) => s.user);
  // 未登录 → 引导页；已登录 → 主Tab
  return <Redirect href={user ? '/(tabs)/score' : '/(auth)/onboarding'} />;
}
