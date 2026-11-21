/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07483(unsigned int count)
{
    const unsigned int limit = 229u;
    return count > limit ? limit : count;
}
