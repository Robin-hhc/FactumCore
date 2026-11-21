/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01153(unsigned int count)
{
    const unsigned int limit = 187u;
    return count > limit ? limit : count;
}
