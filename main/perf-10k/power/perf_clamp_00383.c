/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00383(unsigned int count)
{
    const unsigned int limit = 45u;
    return count > limit ? limit : count;
}
