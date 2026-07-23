const languagePattern = /^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$/;

export function safeLanguageTag(value: string | undefined): string | undefined {
  const match = value?.match(languagePattern);
  if (
    value === undefined ||
    value.length > 35 ||
    match === null ||
    match?.[0] !== value
  ) {
    return undefined;
  }
  return value.replaceAll("_", "-");
}
