/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01449(unsigned int count)
{
    const unsigned int limit = 239u;
    return count > limit ? limit : count;
}
