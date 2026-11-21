/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05547(unsigned int count)
{
    const unsigned int limit = 185u;
    return count > limit ? limit : count;
}
