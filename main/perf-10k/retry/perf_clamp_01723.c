/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01723(unsigned int count)
{
    const unsigned int limit = 166u;
    return count > limit ? limit : count;
}
