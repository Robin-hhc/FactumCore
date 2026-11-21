/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04594(unsigned int count)
{
    const unsigned int limit = 169u;
    return count > limit ? limit : count;
}
