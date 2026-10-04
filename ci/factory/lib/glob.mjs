// Minimal glob matching for policy paths: `**` matches any number of path
// segments, `*` matches within one segment. Paths use forward slashes.
export function globToRegExp(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') {
      // "dir/**" also matches "dir" itself; "**/x" matches "x" at any depth.
      if (glob[i + 2] === '/') {
        re += '(?:.*/)?';
        i += 2;
      } else {
        re += '.*';
        i += 1;
      }
    } else if (c === '*') {
      re += '[^/]*';
    } else if ('.+?^${}()|[]\\'.includes(c)) {
      re += '\\' + c;
    } else {
      re += c;
    }
  }
  return new RegExp('^' + re + '$');
}

export function matches(path, glob) {
  return globToRegExp(glob).test(path);
}

export function matchesAny(path, globs) {
  return globs.some((g) => matches(path, g));
}
