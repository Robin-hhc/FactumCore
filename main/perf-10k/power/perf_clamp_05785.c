/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05785(unsigned int count)
{
    const unsigned int limit = 247u;
    return count > limit ? limit : count;
}
