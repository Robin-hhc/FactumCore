/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03983(unsigned int count)
{
    const unsigned int limit = 240u;
    return count > limit ? limit : count;
}
