// Evaluated by token_usage.py from the runtime package directory so this public
// import uses the project's pinned cligent installation.
import { estimateCost } from '@sublang/cligent';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const requests = JSON.parse(input);
const results = await Promise.all(requests.map(async ({ usage, options }) => {
  try {
    return await estimateCost(usage, options);
  } catch (error) {
    return { status: 'unavailable', reason: 'estimator-error', message: String(error) };
  }
}));
process.stdout.write(JSON.stringify(results));
