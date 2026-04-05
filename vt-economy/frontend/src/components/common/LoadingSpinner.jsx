export default function LoadingSpinner() {
  return (
    <div className="w-full h-full min-h-[120px] flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
